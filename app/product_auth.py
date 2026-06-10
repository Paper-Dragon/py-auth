from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AUTH_MODE_MANUAL,
    AUTH_MODE_OPEN,
    AUTH_MODE_PAID,
    Device,
    Order,
    Product,
)
from app.product_utils import (
    pay_type_from_product,
    plan_detail_from_product,
    plan_from_product,
    software_name_for_product,
)

ORDER_STATUS_PAID = "paid"

PLAN_DISPLAY_NAMES: dict[str, str] = {
    "pro": "Pro",
}


def format_plan_name(plan: str | None) -> str:
    if not plan:
        return ""
    key = plan.strip().lower()
    if key in PLAN_DISPLAY_NAMES:
        return PLAN_DISPLAY_NAMES[key]
    text = plan.strip()
    if text.isascii() and text.isalpha():
        return text.capitalize()
    return text


@dataclass
class AuthEvaluation:
    authorized: bool
    message: str
    plan: str | None = None


def has_paid_order(db: Session, device_id: str, product_key: str) -> bool:
    return (
        db.query(Order)
        .filter(
            Order.device_id == device_id,
            Order.product_key == product_key,
            Order.status == ORDER_STATUS_PAID,
        )
        .first()
        is not None
    )


def get_device_plan(db: Session, device: Device, product: Product | None) -> str | None:
    if not product:
        return None

    order = (
        db.query(Order)
        .filter(
            Order.device_id == device.device_id,
            Order.product_key == product.key,
            Order.status == ORDER_STATUS_PAID,
        )
        .order_by(Order.paid_at.desc())
        .first()
    )
    if order and order.plan:
        return order.plan
    return None


def _initial_authorized_for_product(product: Product) -> bool:
    if not product.is_active:
        return False
    if product.auth_mode == AUTH_MODE_OPEN:
        return True
    return False


def resolve_initial_authorization(product: Product | None) -> bool:
    """新设备初始授权：按 client_secret 对应产品 UUID 的授权策略。"""
    if product is None:
        return False
    return _initial_authorized_for_product(product)


def evaluate_device_authorization(
    db: Session,
    device: Device,
    *,
    product: Product | None = None,
) -> AuthEvaluation:
    """授权规则与套餐均按 client_secret 解析的产品 UUID（product.key）。"""
    if product is None:
        if device.is_authorized:
            return AuthEvaluation(True, "设备已授权")
        return AuthEvaluation(False, "设备未授权")

    plan = get_device_plan(db, device, product)

    if not product.is_active:
        return AuthEvaluation(False, "产品已停用")

    mode = product.auth_mode

    if mode == AUTH_MODE_OPEN:
        message = "设备已授权"
        if product.is_default:
            message = "设备已授权（默认产品）"
        return AuthEvaluation(True, message, plan)

    if mode == AUTH_MODE_MANUAL:
        if device.is_authorized:
            message = "设备已授权"
            if product.is_default:
                message = "设备已授权（默认产品）"
            return AuthEvaluation(True, message, plan)
        if product.is_default:
            return AuthEvaluation(
                False, "设备未授权，请在产品管理中调整默认产品策略或手动授权"
            )
        return AuthEvaluation(False, "设备未授权，请联系管理员审核")

    if mode == AUTH_MODE_PAID:
        if has_paid_order(db, device.device_id, product.key) or device.is_authorized:
            paid_plan = plan or plan_from_product(product)
            return AuthEvaluation(True, "设备已授权", paid_plan)
        return AuthEvaluation(False, "设备未授权，请先完成付款")

    if device.is_authorized:
        return AuthEvaluation(True, "设备已授权", plan)
    return AuthEvaluation(False, "设备未授权")


def build_device_plan_display(
    db: Session,
    device: Device,
    product: Product | None,
    evaluation: AuthEvaluation,
) -> dict[str, str | None]:
    """管理端套餐展示：标签、补充说明与 Tag 类型。"""
    empty = {"plan_label": None, "plan_hint": None, "plan_tag": None}
    if not product:
        return empty

    mode = product.auth_mode
    plan = evaluation.plan
    paid = has_paid_order(db, device.device_id, product.key)

    if mode == AUTH_MODE_PAID:
        target_plan = plan or plan_from_product(product)
        if not evaluation.authorized and not paid:
            return {
                "plan_label": "待付费",
                "plan_hint": format_plan_name(target_plan),
                "plan_tag": "danger",
            }
        return {
            "plan_label": format_plan_name(target_plan),
            "plan_hint": "已付费" if paid else ("手动授权" if device.is_authorized else None),
            "plan_tag": "success" if paid else "warning",
        }

    if mode == AUTH_MODE_OPEN:
        return {
            "plan_label": "默认",
            "plan_hint": "不限",
            "plan_tag": "success",
        }

    if mode == AUTH_MODE_MANUAL:
        if evaluation.authorized:
            return {
                "plan_label": "标准",
                "plan_hint": "手动授权",
                "plan_tag": "success",
            }
        return {
            "plan_label": "待审核",
            "plan_hint": None,
            "plan_tag": "danger",
        }

    if plan:
        return {
            "plan_label": format_plan_name(plan),
            "plan_hint": None,
            "plan_tag": "info",
        }
    return empty


def build_product_plan_info(db: Session, product: Product) -> dict[str, Any]:
    """根据产品配置构建客户端可读的套餐信息。"""
    from app.payment_config import load_epay_config
    from app.services.payment_service import is_payable_product, product_price, validate_pay_type

    plan = plan_from_product(product)
    plan_detail = plan_detail_from_product(product)
    info: dict[str, Any] = {
        "display_name": product.display_name,
        "software_name": software_name_for_product(product) or None,
        "auth_mode": product.auth_mode,
        "plan": plan,
        "plan_detail": plan_detail,
        "can_pay": False,
    }

    if product.auth_mode != AUTH_MODE_PAID:
        return info

    pay_type = pay_type_from_product(product)
    info["pay_type"] = pay_type
    try:
        info["price"] = product_price(product)
    except ValueError:
        return info

    if not is_payable_product(product):
        return info

    config = load_epay_config(db)
    if not config.get("enabled"):
        return info

    try:
        validate_pay_type(pay_type, config)
    except ValueError:
        return info

    info["can_pay"] = True
    return info
