from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    AUTH_MODE_HYBRID,
    AUTH_MODE_MANUAL,
    AUTH_MODE_OPEN,
    AUTH_MODE_PAID,
    AUTH_MODE_TRIAL,
    Device,
    Order,
    Product,
)
from app.product_utils import plan_from_product

ORDER_STATUS_PAID = "paid"


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
    if product.auth_mode == AUTH_MODE_HYBRID:
        return "free"
    return None


def _trial_days(product: Product) -> int:
    config = product.config if isinstance(product.config, dict) else {}
    try:
        days = int(config.get("trial_days", 7))
    except (TypeError, ValueError):
        days = 7
    return max(1, min(days, 3650))


def _is_trial_active(device: Device, product: Product) -> bool:
    anchor = device.created_at or datetime.now()
    expires_at = anchor + timedelta(days=_trial_days(product))
    return datetime.now() < expires_at


def _initial_authorized_for_product(product: Product) -> bool:
    if not product.is_active:
        return False
    if product.auth_mode in (AUTH_MODE_OPEN, AUTH_MODE_TRIAL, AUTH_MODE_HYBRID):
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

    if mode == AUTH_MODE_TRIAL:
        if _is_trial_active(device, product):
            return AuthEvaluation(True, "设备已授权（试用中）", plan)
        return AuthEvaluation(False, "试用已到期")

    if mode == AUTH_MODE_PAID:
        if has_paid_order(db, device.device_id, product.key) or device.is_authorized:
            paid_plan = plan or plan_from_product(product)
            return AuthEvaluation(True, "设备已授权", paid_plan)
        return AuthEvaluation(False, "设备未授权，请先完成付款")

    if mode == AUTH_MODE_HYBRID:
        paid_plan = plan or "free"
        return AuthEvaluation(True, "设备已授权", paid_plan)

    if device.is_authorized:
        return AuthEvaluation(True, "设备已授权", plan)
    return AuthEvaluation(False, "设备未授权")
