import logging
import secrets
import urllib.parse
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.audit import add_operation_log
from app.auth import get_current_user_optional
from app.database import get_db
from app.deps import require_admin
from app.epay import (
    EPAY_PAY_TYPES,
    EPAY_TEST_PRODUCT_KEY,
    MapiResult,
    create_pay_result,
    epay_verify,
    extract_notify_params,
    query_merchant,
    query_order,
)
from app.models import AUTH_MODE_HYBRID, AUTH_MODE_PAID, Device, Order, Product, User
from app.product_resolve import get_product_by_key
from app.product_utils import pay_type_from_product, plan_from_product, software_name_for_product
from app.payment_config import (
    ensure_epay_credentials,
    ensure_epay_ready,
    ensure_pay_type_enabled,
    get_enabled_channels,
    load_epay_config,
    mask_epay_config,
    resolve_notify_url,
    resolve_pay_url,
    resolve_return_url,
    save_epay_config,
)
from app.schemas import (
    EpayConfigResponse,
    EpayConfigUpdate,
    EpayTestConnectionRequest,
    EpayTestConnectionResponse,
    EpayTestPayRequest,
    PaymentDeviceContextResponse,
    PaymentChannelsResponse,
    PaymentOrderCreate,
    PaymentOrderListResponse,
    PaymentOrderPublicResponse,
    PaymentOrderResponse,
    PaymentOrderSummary,
)
from app.rate_limit import require_rate_limit
from app.ws_manager import device_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["支付"])

ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_PAID = "paid"
_ORDER_NOT_FOUND = "订单不存在"

PAY_TYPE_LABELS = {
    "alipay": "支付宝",
    "wxpay": "微信",
    "qqpay": "QQ 钱包",
}


def _format_money(value: str | float | Decimal) -> str:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="金额格式无效")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="金额必须大于 0")
    return format(amount, "f")


def _generate_out_trade_no(*, test: bool = False) -> str:
    prefix = "TEST" if test else "AUTH"
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(4).upper()}"


def _product_price(product: Product) -> str:
    config = product.config if isinstance(product.config, dict) else {}
    return _format_money(str(config.get("price", "0")))


def _is_payable_product(product: Product) -> bool:
    return product.is_active and product.auth_mode in (AUTH_MODE_PAID, AUTH_MODE_HYBRID)


def _payment_device_context(db: Session, device_id: str) -> PaymentDeviceContextResponse:
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
    if not _is_payable_product(product):
        return PaymentDeviceContextResponse(
            device_id=device_id,
            software_name=software_name,
            display_name=product.display_name,
            message="该产品未开启付费授权",
        )

    try:
        price = _product_price(product)
    except HTTPException:
        return PaymentDeviceContextResponse(
            device_id=device_id,
            software_name=software_name,
            display_name=product.display_name,
            message="产品价格未配置",
        )

    pay_type = pay_type_from_product(product)
    config = load_epay_config(db)
    if not config.get("enabled"):
        return PaymentDeviceContextResponse(
            device_id=device_id,
            software_name=software_name,
            display_name=product.display_name,
            price=price,
            pay_type=pay_type,
            message="支付功能未开启",
        )
    try:
        _validate_pay_type(pay_type, config)
    except HTTPException as exc:
        return PaymentDeviceContextResponse(
            device_id=device_id,
            software_name=software_name,
            display_name=product.display_name,
            price=price,
            pay_type=pay_type,
            message=str(exc.detail),
        )

    return PaymentDeviceContextResponse(
        device_id=device_id,
        software_name=software_name,
        display_name=product.display_name,
        price=price,
        pay_type=pay_type,
        can_pay=True,
    )


def _resolve_payable_product(db: Session, device_id: str) -> Product:
    ctx = _payment_device_context(db, device_id)
    if not ctx.can_pay:
        raise HTTPException(status_code=400, detail=ctx.message or "无法确定付费产品")
    device = db.query(Device).filter(Device.device_id == device_id.strip()).first()
    product_key = (device.product_key or "").strip() if device else ""
    product = get_product_by_key(db, product_key)
    if not product or not _is_payable_product(product):
        raise HTTPException(status_code=400, detail="产品不存在或未开启付费")
    return product


def _is_test_order(order: Order) -> bool:
    return order.product_key == EPAY_TEST_PRODUCT_KEY


def _build_epay_config_response(config: dict, base: str) -> EpayConfigResponse:
    masked = mask_epay_config(config)
    return EpayConfigResponse(
        enabled=masked["enabled"],
        api_url=masked.get("api_url", ""),
        pid=masked.get("pid", ""),
        key=masked.get("key", ""),
        key_configured=masked.get("key_configured", False),
        notify_url=masked.get("notify_url", ""),
        return_url=masked.get("return_url", ""),
        sign_mode=str(masked.get("sign_mode", "direct") or "direct"),
        sitename=str(masked.get("sitename", "") or ""),
        enabled_channels=get_enabled_channels(config),
        resolved_notify_url=resolve_notify_url(config, base),
        resolved_return_url=resolve_return_url(config, base),
        resolved_pay_url=resolve_pay_url(config, base, configured_only=True),
    )


def _device_owns_order(order: Order, device_id: str | None) -> bool:
    claimed = (device_id or "").strip()
    return bool(claimed and claimed == order.device_id)


def _epay_amount_matches(order: Order, callback_money: str | None, *, strict: bool = False) -> bool:
    if not callback_money:
        return not strict
    try:
        return _format_money(callback_money) == _format_money(order.money)
    except HTTPException:
        return False


def _epay_params_signed(params: dict[str, str], merchant_key: str, sign_mode: str) -> bool:
    return bool(
        merchant_key
        and params.get("sign")
        and epay_verify(params, merchant_key, sign_mode=sign_mode)
    )


def _to_public_order_response(order: Order) -> PaymentOrderPublicResponse:
    return PaymentOrderPublicResponse(
        out_trade_no=order.out_trade_no,
        status=order.status,
        paid_at=order.paid_at,
        is_test=_is_test_order(order),
    )


def _to_order_response(order: Order, pay_result: MapiResult | None = None) -> PaymentOrderResponse:
    response = PaymentOrderResponse(
        id=order.id,
        out_trade_no=order.out_trade_no,
        trade_no=order.trade_no,
        device_id=order.device_id,
        product_name=order.product_name,
        plan=order.plan,
        money=order.money,
        pay_type=order.pay_type,
        status=order.status,
        is_test=_is_test_order(order),
        created_at=order.created_at,
        paid_at=order.paid_at,
    )
    if pay_result:
        response.pay_mode = pay_result.pay_mode
        response.pay_url = pay_result.pay_url
        response.submit_action = pay_result.submit_action
        response.form_fields = pay_result.form_fields
    return response


def _software_name_for_order(db: Session, order: Order) -> str:
    product = get_product_by_key(db, order.product_key)
    return software_name_for_product(product, fallback=order.product_key)


def _authorize_device_after_payment(db: Session, order: Order) -> None:
    if _is_test_order(order):
        return

    bind_name = _software_name_for_order(db, order)
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


async def _try_sync_order_paid(
    db: Session,
    order: Order,
    request: Request,
    *,
    raise_config_errors: bool = False,
) -> None:
    if order.status == ORDER_STATUS_PAID:
        return
    config = load_epay_config(db)
    try:
        epay = ensure_epay_credentials(
            config,
            _request_base_url(request),
            require_enabled=False,
            require_callbacks=False,
        )
        remote = query_order(epay["api_url"], epay["pid"], epay["key"], order.out_trade_no)
    except ValueError:
        if raise_config_errors:
            raise
        logger.warning("同步易支付订单状态失败: 易支付配置不可用")
        return
    except Exception as exc:
        logger.warning("同步易支付订单状态失败: %s", exc)
        return
    remote_status = str(remote.get("status") or remote.get("trade_status") or "").upper()
    if remote_status in ("TRADE_SUCCESS", "1", "PAID", "SUCCESS"):
        await _mark_order_paid(db, order, str(remote.get("trade_no") or ""))
        db.commit()
        db.refresh(order)


async def _mark_order_paid(db: Session, order: Order, trade_no: str | None) -> bool:
    if order.status == ORDER_STATUS_PAID:
        return False

    order.status = ORDER_STATUS_PAID
    order.trade_no = trade_no or order.trade_no
    order.paid_at = datetime.now()
    order.updated_at = datetime.now()
    _authorize_device_after_payment(db, order)
    return True


def _request_base_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    scheme = forwarded_proto.split(",")[0].strip() if forwarded_proto else request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{scheme}://{host}".rstrip("/")


def _validate_pay_type(pay_type: str, config: dict | None = None) -> str:
    try:
        if config is None:
            normalized = pay_type.strip().lower()
            if normalized not in EPAY_PAY_TYPES:
                raise ValueError("pay_type 仅支持 alipay、wxpay 或 qqpay")
            return normalized
        return ensure_pay_type_enabled(config, pay_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _create_and_submit_order(
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
    out_trade_no = _generate_out_trade_no(test=test)
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
        sign_mode=epay.get("sign_mode", "direct"),
        prefer_mapi=True,
    )
    return order, pay_result


async def _handle_epay_notify(request: Request, db: Session) -> PlainTextResponse:
    form_params = {}
    if request.method.upper() == "POST":
        try:
            body = await request.body()
            if body:
                parsed = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
                form_params = {k: v[-1] if isinstance(v, list) and v else "" for k, v in parsed.items()}
        except Exception:
            form_params = {}

    params = extract_notify_params(
        request.method,
        {k: v for k, v in request.query_params.items()},
        form_params,
    )
    out_trade_no = params.get("out_trade_no", "")
    trade_status = params.get("trade_status", "")
    trade_no = params.get("trade_no")

    config = load_epay_config(db)
    try:
        epay = ensure_epay_ready(config, _request_base_url(request))
    except ValueError:
        logger.warning("易支付回调时配置不可用")
        return PlainTextResponse("fail")

    if not epay_verify(params, epay["key"], sign_mode=epay.get("sign_mode", "direct")):
        logger.warning("易支付回调验签失败: %s", out_trade_no)
        return PlainTextResponse("fail")

    if trade_status != "TRADE_SUCCESS":
        return PlainTextResponse("success")

    order = db.query(Order).filter(Order.out_trade_no == out_trade_no).first()
    if not order:
        logger.warning("易支付回调订单不存在: %s", out_trade_no)
        return PlainTextResponse("fail")

    if not _epay_amount_matches(order, params.get("money")):
        logger.warning("易支付回调金额不一致: %s", out_trade_no)
        return PlainTextResponse("fail")

    changed = await _mark_order_paid(db, order, trade_no)
    if changed:
        add_operation_log(
            db,
            username="system",
            action="payment_success",
            target_type="order",
            target_id=order.out_trade_no,
            detail={
                "device_id": order.device_id,
                "product_key": order.product_key,
                "trade_no": trade_no,
                "money": order.money,
                "is_test": _is_test_order(order),
            },
        )
        if not _is_test_order(order):
            await device_ws_manager.broadcast({
                "type": "devices_changed",
                "action": "payment",
                "device_id": order.device_id,
            })
    db.commit()
    return PlainTextResponse("success")


@router.get("/api/admin/payment/epay", response_model=EpayConfigResponse)
async def get_epay_config(
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = load_epay_config(db)
    return _build_epay_config_response(config, _request_base_url(request))


@router.put("/api/admin/payment/epay", response_model=EpayConfigResponse)
async def update_epay_config(
    data: EpayConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = load_epay_config(db)
    try:
        saved = save_epay_config(db, data.model_dump(exclude_unset=True), existing)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    add_operation_log(
        db,
        username=current_user.username,
        action="update_epay_config",
        target_type="config",
        target_id="epay_config",
        detail={"updated_fields": list(data.model_dump(exclude_unset=True).keys())},
    )
    db.commit()
    return _build_epay_config_response(saved, _request_base_url(request))


@router.post("/api/admin/payment/epay/test-connection", response_model=EpayTestConnectionResponse)
async def test_epay_connection(
    data: EpayTestConnectionRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = load_epay_config(db)
    pay_type = _validate_pay_type(data.pay_type, config)
    label = PAY_TYPE_LABELS.get(pay_type, pay_type)

    try:
        epay = ensure_epay_credentials(
            config,
            _request_base_url(request),
            require_enabled=False,
            require_callbacks=True,
        )
    except ValueError as exc:
        return EpayTestConnectionResponse(success=False, message=str(exc))

    try:
        query_merchant(epay["api_url"], epay["pid"], epay["key"])
    except ValueError as exc:
        return EpayTestConnectionResponse(success=False, message=f"商户接口不可用：{exc}")
    except Exception as exc:
        logger.exception("易支付商户连接测试失败")
        return EpayTestConnectionResponse(success=False, message=f"商户接口连接失败：{exc}")

    try:
        out_trade_no = f"TESTCONN{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3).upper()}"
        pay_result = create_pay_result(
            epay["api_url"],
            pid=epay["pid"],
            merchant_key=epay["key"],
            pay_type=pay_type,
            out_trade_no=out_trade_no,
            notify_url=epay["notify_url"],
            return_url=epay["return_url"],
            name="渠道连接测试",
            money="0.01",
            sitename=epay.get("sitename", ""),
            sign_mode=epay.get("sign_mode", "direct"),
            prefer_mapi=True,
        )
        return EpayTestConnectionResponse(
            success=True,
            message=f"{label}渠道连接正常",
            detail={
                "pay_type": pay_type,
                "pay_mode": pay_result.pay_mode,
                "out_trade_no": out_trade_no,
            },
        )
    except ValueError as exc:
        return EpayTestConnectionResponse(success=False, message=f"{label}渠道不可用：{exc}")
    except Exception as exc:
        logger.exception("易支付渠道连接测试失败: %s", pay_type)
        return EpayTestConnectionResponse(success=False, message=f"{label}渠道测试失败：{exc}")


@router.post("/api/admin/payment/epay/test-pay", response_model=PaymentOrderResponse)
async def test_epay_payment(
    data: EpayTestPayRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    config = load_epay_config(db)
    pay_type = _validate_pay_type(data.pay_type, config)
    money = _format_money(data.money)

    try:
        epay = ensure_epay_credentials(
            config,
            _request_base_url(request),
            require_enabled=False,
            require_callbacks=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    order, pay_result = _create_and_submit_order(
        db=db,
        epay=epay,
        device_id=f"epay_test_{current_user.username}",
        product_key=EPAY_TEST_PRODUCT_KEY,
        product_name="易支付连接测试",
        plan=None,
        money=money,
        pay_type=pay_type,
        test=True,
    )
    add_operation_log(
        db,
        username=current_user.username,
        action="epay_test_pay",
        target_type="order",
        target_id=order.out_trade_no,
        detail={"money": money, "pay_type": pay_type},
    )
    db.commit()
    return _to_order_response(order, pay_result)


def _apply_order_filters(
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


def _build_order_summary(db: Session) -> PaymentOrderSummary:
    total = db.query(Order).count()
    pending = db.query(Order).filter(Order.status == ORDER_STATUS_PENDING).count()
    paid = db.query(Order).filter(Order.status == ORDER_STATUS_PAID).count()
    test = db.query(Order).filter(Order.product_key == EPAY_TEST_PRODUCT_KEY).count()
    return PaymentOrderSummary(total=total, pending=pending, paid=paid, test=test)


@router.get("/api/admin/payment/orders", response_model=PaymentOrderListResponse)
async def list_payment_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(None),
    pay_type: str | None = Query(None),
    keyword: str | None = Query(None),
    test_only: bool | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = _apply_order_filters(
        db.query(Order),
        status=status,
        pay_type=pay_type,
        keyword=keyword,
        test_only=test_only,
    )
    total = query.count()
    orders = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaymentOrderListResponse(
        total=total,
        orders=[_to_order_response(item) for item in orders],
        summary=_build_order_summary(db),
    )


@router.post("/api/admin/payment/orders/{out_trade_no}/sync", response_model=PaymentOrderResponse)
async def sync_payment_order(
    out_trade_no: str,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    order = db.query(Order).filter(Order.out_trade_no == out_trade_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == ORDER_STATUS_PAID:
        return _to_order_response(order)

    try:
        await _try_sync_order_paid(db, order, request, raise_config_errors=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_order_response(order)


@router.get("/api/payment/channels", response_model=PaymentChannelsResponse)
async def list_payment_channels(db: Session = Depends(get_db)):
    config = load_epay_config(db)
    enabled = bool(config.get("enabled"))
    channels = get_enabled_channels(config) if enabled else []
    return PaymentChannelsResponse(enabled=enabled, channels=channels)


@router.get("/api/payment/device-context", response_model=PaymentDeviceContextResponse)
async def get_payment_device_context(
    device_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _: None = Depends(require_rate_limit("payment_order")),
):
    return _payment_device_context(db, device_id)


@router.post("/api/payment/orders", response_model=PaymentOrderResponse)
async def create_payment_order(
    data: PaymentOrderCreate,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_rate_limit("payment_order")),
):
    device_id = data.device_id.strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id 不能为空")

    product = _resolve_payable_product(db, device_id)
    config = load_epay_config(db)
    pay_type = _validate_pay_type(pay_type_from_product(product), config)
    try:
        epay = ensure_epay_ready(config, _request_base_url(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    order, pay_result = _create_and_submit_order(
        db=db,
        epay=epay,
        device_id=device_id,
        product_key=product.key,
        product_name=product.display_name,
        plan=plan_from_product(product) or "pro",
        money=_product_price(product),
        pay_type=pay_type,
        test=False,
    )
    return _to_order_response(order, pay_result)


@router.get(
    "/api/payment/orders/{out_trade_no}",
    response_model=PaymentOrderResponse | PaymentOrderPublicResponse,
)
async def get_payment_order(
    out_trade_no: str,
    request: Request,
    device_id: str | None = Query(
        None,
        min_length=1,
        description="下单设备 ID；非管理员查询时必填且须与订单一致",
    ),
    sync: bool = Query(False, description="是否向易支付查询最新状态"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    order = db.query(Order).filter(Order.out_trade_no == out_trade_no).first()
    if not order:
        raise HTTPException(status_code=404, detail=_ORDER_NOT_FOUND)

    is_admin = bool(current_user and current_user.is_admin)
    if not is_admin and not _device_owns_order(order, device_id):
        raise HTTPException(status_code=404, detail=_ORDER_NOT_FOUND)

    if sync:
        await _try_sync_order_paid(db, order, request)

    if is_admin:
        return _to_order_response(order)
    return _to_public_order_response(order)


@router.api_route("/api/payment/epay/notify", methods=["GET", "POST"])
async def epay_notify(request: Request, db: Session = Depends(get_db)):
    return await _handle_epay_notify(request, db)


def _epay_callback_params(request: Request) -> dict[str, str]:
    """易支付回调参数（排除客户端附加的 device_id，避免破坏验签）。"""
    return {
        key: value
        for key, value in request.query_params.items()
        if key != "device_id"
    }


def _epay_return_pending(out_trade_no: str = "") -> dict:
    return {
        "success": False,
        "out_trade_no": out_trade_no,
        "status": "unknown",
        "is_test": False,
        "message": "支付结果处理中，请稍后刷新",
    }


@router.get("/api/payment/epay/return")
async def epay_return(
    request: Request,
    device_id: str | None = Query(
        None,
        min_length=1,
        description="下单设备 ID；无易支付签名时须与订单一致方可查看结果",
    ),
    db: Session = Depends(get_db),
):
    params = _epay_callback_params(request)
    claimed_device_id = (device_id or "").strip()
    out_trade_no = params.get("out_trade_no", "")

    config = load_epay_config(db)
    merchant_key = str(config.get("key") or "")
    sign_mode = str(config.get("sign_mode", "direct") or "direct")
    has_sign = bool(params.get("sign"))
    signed = _epay_params_signed(params, merchant_key, sign_mode)
    if merchant_key and has_sign and not signed:
        raise HTTPException(status_code=400, detail="支付返回验签失败")

    order = None
    if out_trade_no:
        order = db.query(Order).filter(Order.out_trade_no == out_trade_no).first()

    if (
        order
        and signed
        and params.get("trade_status") == "TRADE_SUCCESS"
        and order.status != ORDER_STATUS_PAID
    ):
        if _epay_amount_matches(order, params.get("money"), strict=True):
            await _mark_order_paid(db, order, params.get("trade_no"))
            db.commit()
        else:
            logger.warning("易支付返回金额校验失败: %s", out_trade_no)

    can_view_status = bool(
        order and (signed or _device_owns_order(order, claimed_device_id))
    )

    if not order or not can_view_status:
        return _epay_return_pending(out_trade_no)

    is_paid = order.status == ORDER_STATUS_PAID
    is_test = _is_test_order(order)
    return {
        "success": is_paid,
        "out_trade_no": out_trade_no,
        "status": order.status,
        "is_test": is_test,
        "message": (
            "支付成功，授权已开通"
            if is_paid and not is_test
            else "支付成功（测试订单）"
            if is_paid and is_test
            else "支付结果处理中，请稍后刷新"
        ),
    }
