"""支付订单领域逻辑。

不依赖 FastAPI：业务错误以 ValueError 抛出，由路由层转换为 HTTP 响应。
负责金额规范、订单创建/同步、回调标记、设备授权联动等。
"""
from __future__ import annotations

import secrets
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.epay import (
    EPAY_PAY_TYPES,
    EPAY_TEST_PRODUCT_KEY,
    MapiResult,
    create_pay_result,
    epay_verify,
    query_order,
)
from app.models import AUTH_MODE_PAID, Device, Order, Product
from app.payment_config import (
    ensure_epay_credentials,
    ensure_pay_type_enabled,
    load_epay_config,
)
from app.product_auth import build_product_plan_info
from app.product_resolve import get_product_by_key
from app.product_utils import (
    pay_type_from_product,
    software_name_for_product,
)
from app.schemas import PaymentDeviceContextResponse, PaymentOrderSummary

ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_PAID = "paid"

PAY_TYPE_LABELS = {
    "alipay": "支付宝",
    "wxpay": "微信",
    "qqpay": "QQ 钱包",
}


def format_money(value: str | float | Decimal) -> str:
    """规范金额为两位小数字符串，非法或非正数抛 ValueError。"""
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError("金额格式无效")
    if amount <= 0:
        raise ValueError("金额必须大于 0")
    return format(amount, "f")


def generate_out_trade_no(*, test: bool = False) -> str:
    prefix = "TEST" if test else "AUTH"
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(4).upper()}"


def product_price(product: Product) -> str:
    config = product.config if isinstance(product.config, dict) else {}
    return format_money(str(config.get("price", "0")))


def is_payable_product(product: Product) -> bool:
    return product.is_active and product.auth_mode == AUTH_MODE_PAID


def is_test_order(order: Order) -> bool:
    return order.product_key == EPAY_TEST_PRODUCT_KEY


def device_owns_order(order: Order, device_id: str | None) -> bool:
    claimed = (device_id or "").strip()
    return bool(claimed and claimed == order.device_id)


def epay_amount_matches(order: Order, callback_money: str | None, *, strict: bool = False) -> bool:
    if not callback_money:
        return not strict
    try:
        return format_money(callback_money) == format_money(order.money)
    except ValueError:
        return False


def epay_params_signed(params: dict[str, str], merchant_key: str) -> bool:
    return bool(
        merchant_key
        and params.get("sign")
        and epay_verify(params, merchant_key)
    )


def validate_pay_type(pay_type: str, config: dict | None = None) -> str:
    """校验支付方式；config 为 None 时只校验取值范围，否则校验是否开通。"""
    if config is None:
        normalized = pay_type.strip().lower()
        if normalized not in EPAY_PAY_TYPES:
            raise ValueError("pay_type 仅支持 alipay、wxpay 或 qqpay")
        return normalized
    return ensure_pay_type_enabled(config, pay_type)


def _plan_fields_from_product(db: Session, product: Product) -> dict:
    plan_info = build_product_plan_info(db, product)
    return {
        "display_name": plan_info.get("display_name"),
        "auth_mode": plan_info.get("auth_mode"),
        "plan": plan_info.get("plan"),
        "plan_detail": plan_info.get("plan_detail"),
        "price": plan_info.get("price"),
        "pay_type": plan_info.get("pay_type"),
    }


def build_payment_device_context(db: Session, device_id: str) -> PaymentDeviceContextResponse:
    """根据设备已绑定的产品 UUID（client_secret 心跳写入）推断可付费产品。"""
    device_id = device_id.strip()
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return PaymentDeviceContextResponse(
            device_id=device_id,
            message="设备不存在，请先完成客户端授权",
        )

    product_key = (device.product_key or "").strip()
    software_name = (device.software_name or "").strip()
    if not product_key:
        return PaymentDeviceContextResponse(
            device_id=device_id,
            software_name=software_name or None,
            message="设备未绑定产品 UUID，请先完成客户端授权",
        )

    product = get_product_by_key(db, product_key)
    if not product:
        return PaymentDeviceContextResponse(
            device_id=device_id,
            software_name=software_name or None,
            message="设备对应的产品不存在",
        )

    plan_fields = _plan_fields_from_product(db, product)
    base = PaymentDeviceContextResponse(
        device_id=device_id,
        software_name=software_name,
        **plan_fields,
    )
    if not is_payable_product(product):
        base.message = "该产品未开启付费授权"
        return base

    try:
        price = product_price(product)
    except ValueError:
        base.message = "产品价格未配置"
        return base

    pay_type = pay_type_from_product(product)
    base.price = price
    base.pay_type = pay_type
    config = load_epay_config(db)
    if not config.get("enabled"):
        base.message = "支付功能未开启"
        return base
    try:
        validate_pay_type(pay_type, config)
    except ValueError as exc:
        base.message = str(exc)
        return base

    base.can_pay = True
    return base


def resolve_payable_product(db: Session, device_id: str) -> Product:
    ctx = build_payment_device_context(db, device_id)
    if not ctx.can_pay:
        raise ValueError(ctx.message or "无法确定付费产品")
    device = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    product_key = (device.product_key or "").strip() if device else ""
    product = get_product_by_key(db, product_key)
    if not product or not is_payable_product(product):
        raise ValueError("产品不存在或未开启付费")
    return product


def software_name_for_order(db: Session, order: Order) -> str:
    product = get_product_by_key(db, order.product_key)
    return software_name_for_product(product, fallback=order.product_key)


def authorize_device_after_payment(db: Session, order: Order) -> None:
    if is_test_order(order):
        return

    bind_name = software_name_for_order(db, order)
    device = db.query(Device).filter(Device.device_id == order.device_id).first()
    if device:
        device.is_authorized = True
        device.product_key = order.product_key
        device.updated_at = datetime.now()
        if not device.software_name:
            device.software_name = bind_name
    else:
        db.add(
            Device(
                device_id=order.device_id,
                product_key=order.product_key,
                software_name=bind_name,
                is_authorized=True,
            )
        )


def mark_order_paid(db: Session, order: Order, trade_no: str | None) -> bool:
    if order.status == ORDER_STATUS_PAID:
        return False

    order.status = ORDER_STATUS_PAID
    order.trade_no = trade_no or order.trade_no
    order.paid_at = datetime.now()
    order.updated_at = datetime.now()
    authorize_device_after_payment(db, order)
    return True


def sync_order_paid(
    db: Session,
    order: Order,
    base_url: str | None,
    *,
    raise_config_errors: bool = False,
    logger=None,
) -> None:
    """向易支付查询订单状态，已支付则落库。"""
    if order.status == ORDER_STATUS_PAID:
        return
    config = load_epay_config(db)
    try:
        epay = ensure_epay_credentials(
            config,
            base_url,
            require_enabled=False,
            require_callbacks=False,
        )
        remote = query_order(epay["api_url"], epay["pid"], epay["key"], order.out_trade_no)
    except ValueError:
        if raise_config_errors:
            raise
        if logger:
            logger.warning("同步易支付订单状态失败: 易支付配置不可用")
        return
    except Exception as exc:
        if logger:
            logger.warning("同步易支付订单状态失败: %s", exc)
        return
    remote_status = str(remote.get("status") or remote.get("trade_status") or "").strip().upper()
    if remote_status in ("TRADE_SUCCESS", "1", "2", "PAID", "SUCCESS", "PAY_SUCCESS", "COMPLETED"):
        mark_order_paid(db, order, str(remote.get("trade_no") or ""))
        db.commit()
        db.refresh(order)


def create_and_submit_order(
    *,
    db: Session,
    epay: dict[str, str],
    device_id: str,
    product_key: str,
    product_name: str,
    plan: str | None,
    money: str,
    pay_type: str,
    test: bool = False,
) -> tuple[Order, MapiResult]:
    out_trade_no = generate_out_trade_no(test=test)
    order = Order(
        out_trade_no=out_trade_no,
        device_id=device_id,
        product_key=product_key,
        product_name=product_name,
        plan=plan,
        money=money,
        pay_type=pay_type,
        status=ORDER_STATUS_PENDING,
        param=out_trade_no,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    try:
        pay_result = create_pay_result(
            epay["api_url"],
            pid=epay["pid"],
            merchant_key=epay["key"],
            pay_type=pay_type,
            out_trade_no=out_trade_no,
            notify_url=epay["notify_url"],
            return_url=epay["return_url"],
            name=product_name,
            money=money,
            sitename=epay.get("sitename", ""),
            order_mode=epay.get("order_mode", "mapi"),
        )
    except ValueError:
        db.delete(order)
        db.commit()
        raise
    return order, pay_result


def apply_order_filters(
    query,
    *,
    status: str | None,
    pay_type: str | None,
    keyword: str | None,
    test_only: bool | None,
):
    if status:
        query = query.filter(Order.status == status)
    if pay_type:
        query = query.filter(Order.pay_type == pay_type.strip().lower())
    if test_only is True:
        query = query.filter(Order.product_key == EPAY_TEST_PRODUCT_KEY)
    elif test_only is False:
        query = query.filter(Order.product_key != EPAY_TEST_PRODUCT_KEY)
    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.filter(
            (Order.out_trade_no.like(kw))
            | (Order.device_id.like(kw))
            | (Order.trade_no.like(kw))
            | (Order.product_name.like(kw))
            | (Order.product_key.like(kw))
        )
    return query


def build_order_summary(db: Session) -> PaymentOrderSummary:
    total = db.query(Order).count()
    pending = db.query(Order).filter(Order.status == ORDER_STATUS_PENDING).count()
    paid = db.query(Order).filter(Order.status == ORDER_STATUS_PAID).count()
    test = db.query(Order).filter(Order.product_key == EPAY_TEST_PRODUCT_KEY).count()
    return PaymentOrderSummary(total=total, pending=pending, paid=paid, test=test)
