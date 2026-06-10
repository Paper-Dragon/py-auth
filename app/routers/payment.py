import logging
import secrets
import urllib.parse
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.audit import add_operation_log
from app.auth import get_current_user_optional
from app.database import get_db
from app.deps import require_admin
from app.epay import (
    EPAY_TEST_PRODUCT_KEY,
    MapiResult,
    create_pay_result,
    epay_verify,
    extract_notify_params,
    query_merchant,
)
from app.models import Order, User
from app.payment_config import (
    ensure_epay_credentials,
    ensure_epay_ready,
    get_enabled_channels,
    load_epay_config,
    resolve_notify_url,
    resolve_pay_url,
    resolve_return_url,
    save_epay_config,
)
from app.product_utils import pay_type_from_product, plan_from_product
from app.rate_limit import require_rate_limit
from app.schemas import (
    EpayConfigResponse,
    EpayConfigUpdate,
    EpayTestConnectionRequest,
    EpayTestConnectionResponse,
    EpayTestPayRequest,
    PaymentChannelsResponse,
    PaymentDeviceContextResponse,
    PaymentOrderCreate,
    PaymentOrderListResponse,
    PaymentOrderPublicResponse,
    PaymentOrderResponse,
)
from app.services import payment_service as svc
from app.ws_manager import device_ws_manager

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/api/admin/payment", tags=["支付"])
public_router = APIRouter(prefix="/api/payment", tags=["支付"])

_ORDER_NOT_FOUND = "订单不存在"


def _format_money(value) -> str:
    try:
        return svc.format_money(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _validate_pay_type(pay_type: str, config: dict | None = None) -> str:
    try:
        return svc.validate_pay_type(pay_type, config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _request_base_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    scheme = forwarded_proto.split(",")[0].strip() if forwarded_proto else request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{scheme}://{host}".rstrip("/")


def _build_epay_config_response(config: dict, base: str) -> EpayConfigResponse:
    key = str(config.get("key") or "")
    return EpayConfigResponse(
        enabled=bool(config.get("enabled")),
        api_url=config.get("api_url", ""),
        pid=config.get("pid", ""),
        key=key,
        key_configured=bool(key),
        notify_url=config.get("notify_url", ""),
        return_url=config.get("return_url", ""),
        order_mode=str(config.get("order_mode", "mapi") or "mapi"),
        sitename=str(config.get("sitename", "") or ""),
        enabled_channels=get_enabled_channels(config),
        resolved_notify_url=resolve_notify_url(config, base),
        resolved_return_url=resolve_return_url(config, base),
        resolved_pay_url=resolve_pay_url(config, base, configured_only=True),
    )


def _to_public_order_response(order: Order) -> PaymentOrderPublicResponse:
    return PaymentOrderPublicResponse(
        out_trade_no=order.out_trade_no,
        status=order.status,
        paid_at=order.paid_at,
        is_test=svc.is_test_order(order),
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
        is_test=svc.is_test_order(order),
        created_at=order.created_at,
        paid_at=order.paid_at,
    )
    if pay_result:
        response.pay_mode = pay_result.pay_mode
        response.pay_url = pay_result.pay_url
        response.submit_action = pay_result.submit_action
        response.form_fields = pay_result.form_fields
        response.qr_content = pay_result.qr_content
        response.qr_image = pay_result.qr_image
    return response


# ---------------------------------------------------------------------------
# 管理端：易支付配置与订单
# ---------------------------------------------------------------------------


@admin_router.get("/epay", response_model=EpayConfigResponse)
async def get_epay_config(
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = load_epay_config(db)
    return _build_epay_config_response(config, _request_base_url(request))


@admin_router.put("/epay", response_model=EpayConfigResponse)
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


@admin_router.post("/epay/test-connection", response_model=EpayTestConnectionResponse)
async def test_epay_connection(
    data: EpayTestConnectionRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    config = load_epay_config(db)
    pay_type = _validate_pay_type(data.pay_type, config)
    label = svc.PAY_TYPE_LABELS.get(pay_type, pay_type)

    try:
        epay = ensure_epay_credentials(
            config,
            _request_base_url(request),
            require_enabled=False,
            require_callbacks=True,
        )
    except ValueError as exc:
        return EpayTestConnectionResponse(success=False, message=str(exc))

    merchant_query_skipped = False
    try:
        merchant_info = query_merchant(
            epay["api_url"],
            epay["pid"],
            epay["key"],
            optional=True,
        )
        merchant_query_skipped = merchant_info is None
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
            order_mode=epay.get("order_mode", "mapi"),
        )
        success_message = f"{label}渠道连接正常"
        if merchant_query_skipped:
            success_message += "（网关未提供商户查询接口，已直接验证下单）"
        return EpayTestConnectionResponse(
            success=True,
            message=success_message,
            detail={
                "pay_type": pay_type,
                "pay_mode": pay_result.pay_mode,
                "out_trade_no": out_trade_no,
                "merchant_query_skipped": merchant_query_skipped,
            },
        )
    except ValueError as exc:
        return EpayTestConnectionResponse(success=False, message=f"{label}渠道不可用：{exc}")
    except Exception as exc:
        logger.exception("易支付渠道连接测试失败: %s", pay_type)
        return EpayTestConnectionResponse(success=False, message=f"{label}渠道测试失败：{exc}")


@admin_router.post("/epay/test-pay", response_model=PaymentOrderResponse)
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

    try:
        order, pay_result = svc.create_and_submit_order(
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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


@admin_router.get("/orders", response_model=PaymentOrderListResponse)
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
    query = svc.apply_order_filters(
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
        summary=svc.build_order_summary(db),
    )


@admin_router.post("/orders/{out_trade_no}/sync", response_model=PaymentOrderResponse)
async def sync_payment_order(
    out_trade_no: str,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    order = db.query(Order).filter(Order.out_trade_no == out_trade_no).first()
    if not order:
        raise HTTPException(status_code=404, detail=_ORDER_NOT_FOUND)
    if order.status == svc.ORDER_STATUS_PAID:
        return _to_order_response(order)

    try:
        svc.sync_order_paid(
            db, order, _request_base_url(request), raise_config_errors=True, logger=logger
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_order_response(order)


# ---------------------------------------------------------------------------
# 公开端：渠道、下单、查询、易支付回调
# ---------------------------------------------------------------------------


@public_router.get("/channels", response_model=PaymentChannelsResponse)
async def list_payment_channels(db: Session = Depends(get_db)):
    config = load_epay_config(db)
    enabled = bool(config.get("enabled"))
    channels = get_enabled_channels(config) if enabled else []
    return PaymentChannelsResponse(enabled=enabled, channels=channels)


@public_router.get("/device-context", response_model=PaymentDeviceContextResponse)
async def get_payment_device_context(
    device_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _: None = Depends(require_rate_limit("payment_order")),
):
    return svc.build_payment_device_context(db, device_id)


@public_router.post("/orders", response_model=PaymentOrderResponse)
async def create_payment_order(
    data: PaymentOrderCreate,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_rate_limit("payment_order")),
):
    device_id = data.device_id.strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id 不能为空")

    try:
        product = svc.resolve_payable_product(db, device_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config = load_epay_config(db)
    pay_type = _validate_pay_type(pay_type_from_product(product), config)
    try:
        epay = ensure_epay_ready(config, _request_base_url(request))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        order, pay_result = svc.create_and_submit_order(
            db=db,
            epay=epay,
            device_id=device_id,
            product_key=product.key,
            product_name=product.display_name,
            plan=plan_from_product(product) or "pro",
            money=svc.product_price(product),
            pay_type=pay_type,
            test=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_order_response(order, pay_result)


@public_router.get(
    "/orders/{out_trade_no}",
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
    if not is_admin and not svc.device_owns_order(order, device_id):
        raise HTTPException(status_code=404, detail=_ORDER_NOT_FOUND)

    if sync:
        svc.sync_order_paid(db, order, _request_base_url(request), logger=logger)

    if is_admin:
        return _to_order_response(order)
    return _to_public_order_response(order)


async def _handle_epay_notify(request: Request, db: Session) -> PlainTextResponse:
    form_params: dict[str, str] = {}
    if request.method.upper() == "POST":
        try:
            body = await request.body()
            if body:
                parsed = urllib.parse.parse_qs(
                    body.decode("utf-8", errors="replace"), keep_blank_values=True
                )
                form_params = {
                    k: v[-1] if isinstance(v, list) and v else "" for k, v in parsed.items()
                }
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

    if not epay_verify(params, epay["key"]):
        logger.warning("易支付回调验签失败: %s", out_trade_no)
        return PlainTextResponse("fail")

    if trade_status != "TRADE_SUCCESS":
        return PlainTextResponse("success")

    order = db.query(Order).filter(Order.out_trade_no == out_trade_no).first()
    if not order:
        logger.warning("易支付回调订单不存在: %s", out_trade_no)
        return PlainTextResponse("fail")

    if not svc.epay_amount_matches(order, params.get("money")):
        logger.warning("易支付回调金额不一致: %s", out_trade_no)
        return PlainTextResponse("fail")

    changed = svc.mark_order_paid(db, order, trade_no)
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
                "is_test": svc.is_test_order(order),
            },
        )
        if not svc.is_test_order(order):
            await device_ws_manager.broadcast({
                "type": "devices_changed",
                "action": "payment",
                "device_id": order.device_id,
            })
    db.commit()
    return PlainTextResponse("success")


@public_router.api_route("/epay/notify", methods=["GET", "POST"])
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


@public_router.get("/epay/return")
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
    has_sign = bool(params.get("sign"))
    signed = svc.epay_params_signed(params, merchant_key)
    if merchant_key and has_sign and not signed:
        raise HTTPException(status_code=400, detail="支付返回验签失败")

    order = None
    if out_trade_no:
        order = db.query(Order).filter(Order.out_trade_no == out_trade_no).first()

    if (
        order
        and signed
        and params.get("trade_status") == "TRADE_SUCCESS"
        and order.status != svc.ORDER_STATUS_PAID
    ):
        if svc.epay_amount_matches(order, params.get("money"), strict=True):
            svc.mark_order_paid(db, order, params.get("trade_no"))
            db.commit()
        else:
            logger.warning("易支付返回金额校验失败: %s", out_trade_no)

    can_view_status = bool(
        order and (signed or svc.device_owns_order(order, claimed_device_id))
    )

    if not order or not can_view_status:
        return _epay_return_pending(out_trade_no)

    is_paid = order.status == svc.ORDER_STATUS_PAID
    is_test = svc.is_test_order(order)
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
