import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import segno

logger = logging.getLogger(__name__)

EPAY_PAY_TYPES = frozenset({"alipay", "wxpay", "qqpay"})
ORDER_MODE_MAPI = "mapi"
ORDER_MODE_SUBMIT = "submit"
EPAY_ORDER_MODES = frozenset({ORDER_MODE_MAPI, ORDER_MODE_SUBMIT})
EPAY_TEST_PRODUCT_KEY = "__epay_test__"
MAPI_SUCCESS_CODES = {1, "1", 200, "200"}

# mapi.php 返回的支付模式
PAY_MODE_REDIRECT = "redirect"  # 跳转到支付页（alipay 等返回 payurl）
PAY_MODE_FORM = "form"          # 表单自动提交（submit.php）
PAY_MODE_QRCODE = "qrcode"      # 扫码支付（wxpay/qqpay 返回 qrcode/code_url）


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
    """将二维码内容编码为可直接用于 <img src> 的 SVG data URI。"""
    qr = segno.make(content, error="m")
    return qr.svg_data_uri(scale=6, border=2)


def epay_sign(params: dict[str, Any], merchant_key: str) -> str:
    """易支付签名：参数按 ASCII 排序拼接 key=value（剔除 sign/sign_type/空值），末尾接密钥后 MD5。"""
    items: list[str] = []
    for key in sorted(params.keys()):
        if key in ("sign", "sign_type"):
            continue
        value = params[key]
        if value is None or value == "":
            continue
        items.append(f"{key}={value}")
    sign_str = "&".join(items)
    raw = sign_str + merchant_key
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def epay_verify(params: dict[str, Any], merchant_key: str) -> bool:
    received = str(params.get("sign", "")).lower()
    if not received:
        return False
    expected = epay_sign(params, merchant_key)
    return received == expected


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

    payload: dict[str, str] = {
        "pid": str(pid),
        "type": pay_type,
        "out_trade_no": out_trade_no,
        "notify_url": notify_url,
        "return_url": return_url,
        "name": name[:127],
        "money": money,
        "sign_type": "MD5",
    }
    site = (sitename or "").strip()
    if site:
        payload["sitename"] = site[:127]

    payload["sign"] = epay_sign(payload, merchant_key)
    return payload


def build_submit_action(api_url: str) -> str:
    return f"{api_url.rstrip('/')}/submit.php"


def build_mapi_endpoint(api_url: str) -> str:
    return f"{api_url.rstrip('/')}/mapi.php"


def _http_post_form(url: str, fields: dict[str, str], timeout: int = 20) -> str:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _http_get(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_json_body(body: str) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.error("易支付响应非 JSON: %s", body[:500])
        raise ValueError("易支付接口返回格式异常") from exc
    if not isinstance(parsed, dict):
        raise ValueError("易支付接口返回格式异常")
    return parsed


def query_merchant(api_url: str, pid: str, merchant_key: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"act": "query", "pid": str(pid), "key": merchant_key})
    url = f"{api_url.rstrip('/')}/api.php?{query}"
    try:
        body = _http_get(url)
    except urllib.error.URLError as exc:
        logger.error("易支付商户查询失败: %s", exc)
        raise ValueError(f"无法连接易支付接口: {exc}") from exc

    body = body.strip()
    if not body:
        raise ValueError("易支付商户查询返回为空")

    if body.startswith("{"):
        result = _parse_json_body(body)
        code = result.get("code")
        if code not in MAPI_SUCCESS_CODES and str(result.get("status", "")).lower() not in ("success", "1"):
            message = result.get("msg") or result.get("message") or "商户查询失败"
            raise ValueError(str(message))
        return result

    return {"code": 200, "msg": "连接成功", "raw": body[:500]}


def query_order(api_url: str, pid: str, merchant_key: str, out_trade_no: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({
        "act": "order",
        "pid": str(pid),
        "key": merchant_key,
        "out_trade_no": out_trade_no,
    })
    url = f"{api_url.rstrip('/')}/api.php?{query}"
    try:
        body = _http_get(url)
    except urllib.error.URLError as exc:
        raise ValueError(f"订单查询失败: {exc}") from exc
    if body.strip().startswith("{"):
        return _parse_json_body(body)
    return {"code": 200, "msg": "查询完成", "raw": body[:500]}


def request_mapi_pay(
    api_url: str,
    params: dict[str, str],
    *,
    merchant_key: str,
    sitename: str = "",
) -> MapiResult:
    signed = build_order_params(
        pid=params["pid"],
        merchant_key=merchant_key,
        pay_type=params["type"],
        out_trade_no=params["out_trade_no"],
        notify_url=params["notify_url"],
        return_url=params["return_url"],
        name=params["name"],
        money=params["money"],
        sitename=sitename,
    )
    endpoint = build_mapi_endpoint(api_url)
    try:
        body = _http_post_form(endpoint, signed)
    except urllib.error.URLError as exc:
        logger.error("易支付 mapi 请求失败: %s", exc)
        raise ValueError(f"易支付 mapi 请求失败: {exc}") from exc

    result = _parse_json_body(body)
    code = result.get("code")
    if code not in MAPI_SUCCESS_CODES:
        message = result.get("msg") or result.get("message") or "易支付下单失败"
        raise ValueError(str(message))

    # payurl：可直接跳转的收银台页面（支付宝等）
    pay_url = result.get("payurl") or result.get("url")
    if pay_url:
        return MapiResult(pay_mode=PAY_MODE_REDIRECT, pay_url=str(pay_url), raw=result)

    # qrcode：原始支付串，需要前端渲染成二维码供扫码（微信/QQ）
    qrcode = result.get("qrcode")
    code_url = result.get("code_url") or result.get("img")
    if qrcode:
        qr_content = str(qrcode)
        # code_url 若是现成的二维码图片地址则直接用，否则本地按内容生成
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

    # 仅返回二维码图片地址（无原始串）
    if code_url:
        if _is_http_url(str(code_url)):
            return MapiResult(pay_mode=PAY_MODE_QRCODE, qr_image=str(code_url), raw=result)
        return MapiResult(
            pay_mode=PAY_MODE_QRCODE,
            qr_content=str(code_url),
            qr_image=build_qr_data_uri(str(code_url)),
            raw=result,
        )

    # urlscheme：唤起 App 的 scheme，桌面浏览器无法跳转，仅作兜底
    urlscheme = result.get("urlscheme")
    if urlscheme:
        return MapiResult(pay_mode=PAY_MODE_REDIRECT, pay_url=str(urlscheme), raw=result)

    raise ValueError("易支付接口未返回支付信息")


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
    """按 order_mode 选择下单方式：mapi（API 接口）或 submit（页面跳转），两者互相独立、互不回退。"""
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
            sitename=sitename,
        )
        return build_submit_pay(api_url, signed)

    base = {
        "pid": str(pid),
        "type": pay_type,
        "out_trade_no": out_trade_no,
        "notify_url": notify_url,
        "return_url": return_url,
        "name": name,
        "money": money,
    }
    return request_mapi_pay(
        api_url,
        base,
        merchant_key=merchant_key,
        sitename=sitename,
    )


def extract_notify_params(request_method: str, query_params: dict[str, str], form_params: dict[str, str]) -> dict[str, str]:
    if request_method.upper() == "POST" and form_params:
        return dict(form_params)
    return dict(query_params)
