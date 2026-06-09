import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

EPAY_PAY_TYPES = frozenset({"alipay", "wxpay", "qqpay"})
SIGN_MODE_DIRECT = "direct"
SIGN_MODE_WITH_KEY = "with_key"
EPAY_TEST_PRODUCT_KEY = "__epay_test__"
MAPI_SUCCESS_CODES = {1, "1", 200, "200"}


@dataclass
class MapiResult:
    pay_mode: str
    pay_url: str | None = None
    submit_action: str | None = None
    form_fields: dict[str, str] | None = None
    raw: dict[str, Any] | None = None


def epay_sign(params: dict[str, Any], merchant_key: str, *, sign_mode: str = SIGN_MODE_DIRECT) -> str:
    items: list[str] = []
    for key in sorted(params.keys()):
        if key in ("sign", "sign_type"):
            continue
        value = params[key]
        if value is None or value == "":
            continue
        items.append(f"{key}={value}")
    sign_str = "&".join(items)
    if sign_mode == SIGN_MODE_WITH_KEY:
        raw = f"{sign_str}&key={merchant_key}" if sign_str else f"key={merchant_key}"
    else:
        raw = sign_str + merchant_key
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def epay_verify(params: dict[str, Any], merchant_key: str, *, sign_mode: str = SIGN_MODE_DIRECT) -> bool:
    received = str(params.get("sign", "")).lower()
    if not received:
        return False
    expected = epay_sign(params, merchant_key, sign_mode=sign_mode)
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
    sign_mode: str = SIGN_MODE_DIRECT,
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

    payload["sign"] = epay_sign(payload, merchant_key, sign_mode=sign_mode)
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
    sign_mode: str = SIGN_MODE_DIRECT,
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
        sign_mode=sign_mode,
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

    pay_url = result.get("payurl") or result.get("qrcode") or result.get("code_url") or result.get("url")
    if pay_url:
        return MapiResult(pay_mode="redirect", pay_url=str(pay_url), raw=result)

    return build_submit_pay(api_url, signed, raw=result)


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
        pay_mode="form",
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
    sign_mode: str = SIGN_MODE_DIRECT,
    prefer_mapi: bool = True,
) -> MapiResult:
    base = {
        "pid": str(pid),
        "type": pay_type,
        "out_trade_no": out_trade_no,
        "notify_url": notify_url,
        "return_url": return_url,
        "name": name,
        "money": money,
    }
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
        sign_mode=sign_mode,
    )

    if prefer_mapi:
        try:
            return request_mapi_pay(
                api_url,
                base,
                merchant_key=merchant_key,
                sign_mode=sign_mode,
                sitename=sitename,
            )
        except Exception as exc:
            logger.warning("易支付 mapi 下单失败，回退 submit 表单: %s", exc)

    return build_submit_pay(api_url, signed)


def extract_notify_params(request_method: str, query_params: dict[str, str], form_params: dict[str, str]) -> dict[str, str]:
    if request_method.upper() == "POST" and form_params:
        return dict(form_params)
    return dict(query_params)
