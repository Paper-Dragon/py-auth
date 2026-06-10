import logging
from dataclasses import dataclass
from typing import Any

import segno

from app import ezfpy_sdk as sdk

logger = logging.getLogger(__name__)
EPAY_PAY_TYPES = frozenset({"alipay", "wxpay", "qqpay"})
ORDER_MODE_MAPI = "mapi"
ORDER_MODE_SUBMIT = "submit"
EPAY_ORDER_MODES = frozenset({ORDER_MODE_MAPI, ORDER_MODE_SUBMIT})
EPAY_TEST_PRODUCT_KEY = "__epay_test__"
PAY_MODE_REDIRECT = "redirect"
PAY_MODE_FORM = "form"
PAY_MODE_QRCODE = "qrcode"


@dataclass
class MapiResult:
    pay_mode: str
    pay_url: str | None = None
    submit_action: str | None = None
    form_fields: dict[str, str] | None = None
    qr_content: str | None = None
    qr_image: str | None = None
    raw: dict[str, Any] | None = None


def _is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def build_qr_data_uri(content: str) -> str:
    qr = segno.make(content, error="m")
    return qr.svg_data_uri(scale=6, border=2)


def normalize_epay_api_url(api_url: str) -> str:
    return sdk.normalize_base_url(api_url)


def build_submit_action(api_url: str) -> str:
    return f"{normalize_epay_api_url(api_url)}/submit.php"


def build_mapi_endpoint(api_url: str) -> str:
    return f"{normalize_epay_api_url(api_url)}/mapi.php"


def epay_sign(params: dict[str, Any], merchant_key: str) -> str:
    return sdk.calc_sign(
        sdk.build_sign_string(
            money=str(params.get("money", "")),
            name=str(params.get("name", "")),
            notify_url=str(params.get("notify_url", "")),
            out_trade_no=str(params.get("out_trade_no", "")),
            pid=str(params.get("pid", "")),
            return_url=str(params.get("return_url", "")),
            sitename=str(params.get("sitename", "")),
            pay_type=str(params.get("type", "")),
        ),
        merchant_key,
    )


def epay_verify(params: dict[str, Any], merchant_key: str) -> bool:
    return sdk.verify_sign(params, merchant_key)


def build_order_params(
    *,
    pid: str,
    merchant_key: str,
    pay_type: str,
    out_trade_no: str,
    notify_url: str,
    return_url: str,
    name: str,
    money: str,
    sitename: str = "",
) -> dict[str, str]:
    if pay_type not in EPAY_PAY_TYPES:
        raise ValueError(f"不支持的支付方式: {pay_type}")
    return sdk.build_signed_fields(
        money=money,
        name=name[:127],
        notify_url=notify_url,
        out_trade_no=out_trade_no,
        pid=str(pid),
        return_url=return_url,
        sitename=(sitename or "")[:127],
        pay_type=pay_type,
        key=merchant_key,
    )


def query_merchant(
    api_url: str,
    pid: str,
    merchant_key: str,
    *,
    optional: bool = False,
) -> dict[str, Any] | None:
    return sdk.act(api_url, str(pid), merchant_key, optional=optional)


def query_order(api_url: str, pid: str, merchant_key: str, out_trade_no: str) -> dict[str, Any]:
    del pid, merchant_key
    return sdk.order(api_url, out_trade_no)


def _mapi_result_from_response(result: dict[str, Any]) -> MapiResult:
    pay_url = result.get("payurl") or result.get("url")
    if pay_url:
        return MapiResult(pay_mode=PAY_MODE_REDIRECT, pay_url=str(pay_url), raw=result)
    qrcode = result.get("qrcode")
    code_url = result.get("code_url") or result.get("img")
    if qrcode:
        qr_content = str(qrcode)
        if code_url and _is_http_url(str(code_url)):
            qr_image = str(code_url)
        else:
            qr_image = build_qr_data_uri(qr_content)
        return MapiResult(
            pay_mode=PAY_MODE_QRCODE,
            qr_content=qr_content,
            qr_image=qr_image,
            raw=result,
        )
    if code_url:
        if _is_http_url(str(code_url)):
            return MapiResult(pay_mode=PAY_MODE_QRCODE, qr_image=str(code_url), raw=result)
        return MapiResult(
            pay_mode=PAY_MODE_QRCODE,
            qr_content=str(code_url),
            qr_image=build_qr_data_uri(str(code_url)),
            raw=result,
        )
    urlscheme = result.get("urlscheme")
    if urlscheme:
        return MapiResult(pay_mode=PAY_MODE_REDIRECT, pay_url=str(urlscheme), raw=result)
    raise ValueError("易支付接口未返回支付信息")


def request_mapi_pay(
    api_url: str,
    params: dict[str, str],
    *,
    merchant_key: str,
    sitename: str = "",
) -> MapiResult:
    result = sdk.mapi(
        api_url,
        money=params["money"],
        name=params["name"],
        notify_url=params["notify_url"],
        out_trade_no=params["out_trade_no"],
        pay_type=params["type"],
        pid=params["pid"],
        return_url=params["return_url"],
        sitename=sitename,
        key=merchant_key,
    )
    return _mapi_result_from_response(result)


def build_submit_pay(
    api_url: str,
    signed_params: dict[str, str],
    *,
    raw: dict[str, Any] | None = None,
) -> MapiResult:
    action = build_submit_action(api_url)
    fields = {k: v for k, v in signed_params.items() if k != "sign" or v}
    fields["sign"] = signed_params["sign"]
    fields["sign_type"] = signed_params.get("sign_type", "MD5")
    return MapiResult(
        pay_mode=PAY_MODE_FORM,
        submit_action=action,
        form_fields=fields,
        raw=raw,
    )


def create_pay_result(
    api_url: str,
    *,
    pid: str,
    merchant_key: str,
    pay_type: str,
    out_trade_no: str,
    notify_url: str,
    return_url: str,
    name: str,
    money: str,
    sitename: str = "",
    order_mode: str = ORDER_MODE_MAPI,
) -> MapiResult:
    site = sitename or ""
    if order_mode == ORDER_MODE_SUBMIT:
        signed = build_order_params(
            pid=pid,
            merchant_key=merchant_key,
            pay_type=pay_type,
            out_trade_no=out_trade_no,
            notify_url=notify_url,
            return_url=return_url,
            name=name,
            money=money,
            sitename=site,
        )
        return build_submit_pay(api_url, signed)
    return request_mapi_pay(
        api_url,
        {
            "pid": str(pid),
            "type": pay_type,
            "out_trade_no": out_trade_no,
            "notify_url": notify_url,
            "return_url": return_url,
            "name": name,
            "money": money,
        },
        merchant_key=merchant_key,
        sitename=site,
    )


def extract_notify_params(request_method: str, query_params: dict[str, str], form_params: dict[str, str]) -> dict[str, str]:
    if request_method.upper() == "POST" and form_params:
        return dict(form_params)
    return dict(query_params)
