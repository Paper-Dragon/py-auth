"""ezfpy 官方 Python SDK（源自 https://www.ezfpy.cn/download/python.zip）。
线上网关实际可用接口：
- submit.php：页面跳转支付（SDK pay）
- mapi.php：API 支付（官方文档）
- api/findorder：单笔订单查询（api.php?act=order 线上不可用）
- api.php?act=query：商户查询（线上不可用，连接测试时跳过）
"""
from __future__ import annotations

import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)
SUCCESS_CODES = {1, "1", 200, "200"}


def normalize_base_url(api_url: str) -> str:
    url = (api_url or "").strip().rstrip("/")
    if not url:
        return ""
    lowered = url.lower()
    for suffix in ("/mapi.php", "/submit.php", "/api.php", "/api/findorder"):
        if lowered.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
            lowered = url.lower()
    return url


def build_sign_string(
    *,
    money: str,
    name: str,
    notify_url: str,
    out_trade_no: str,
    pid: str,
    return_url: str,
    sitename: str,
    pay_type: str,
) -> str:
    """与官方 python/pay.txt 中 sg 拼接顺序一致。"""
    return (
        f"money={money}&name={name}&notify_url={notify_url}"
        f"&out_trade_no={out_trade_no}&pid={pid}&return_url={return_url}"
        f"&sitename={sitename}&type={pay_type}"
    )


def calc_sign(sign_string: str, key: str) -> str:
    return hashlib.md5((sign_string + key).encode("utf-8")).hexdigest()


def build_signed_fields(
    *,
    money: str,
    name: str,
    notify_url: str,
    out_trade_no: str,
    pid: str,
    return_url: str,
    sitename: str,
    pay_type: str,
    key: str,
) -> dict[str, str]:
    sg = build_sign_string(
        money=money,
        name=name,
        notify_url=notify_url,
        out_trade_no=out_trade_no,
        pid=pid,
        return_url=return_url,
        sitename=sitename,
        pay_type=pay_type,
    )
    return {
        "money": money,
        "name": name,
        "notify_url": notify_url,
        "out_trade_no": out_trade_no,
        "pid": str(pid),
        "return_url": return_url,
        "sitename": sitename,
        "type": pay_type,
        "sign": calc_sign(sg, key),
        "sign_type": "MD5",
    }


def verify_sign(params: dict[str, Any], key: str) -> bool:
    """验签：回调/通知参数按 ASCII 排序（与官方文档一致）。"""
    received = str(params.get("sign", "")).lower()
    if not received:
        return False
    items: list[str] = []
    for field in sorted(params.keys()):
        if field in ("sign", "sign_type"):
            continue
        value = params[field]
        if value is None or value == "":
            continue
        items.append(f"{field}={value}")
    expected = calc_sign("&".join(items), key)
    return received == expected


def _http_get(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _http_post(url: str, fields: dict[str, str] | None = None, timeout: int = 20) -> str:
    data = urllib.parse.urlencode(fields or {}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data if fields else None,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"} if fields else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_json(body: str) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("易支付接口返回格式异常") from exc
    if not isinstance(parsed, dict):
        raise ValueError("易支付接口返回格式异常")
    return parsed


def pay(
    api_url: str,
    *,
    money: str,
    name: str,
    notify_url: str,
    out_trade_no: str,
    pay_type: str,
    pid: str,
    return_url: str,
    sitename: str,
    key: str,
) -> str:
    """发起页面跳转支付：POST submit.php?...（与官方 SDK pay 一致）。"""
    base = normalize_base_url(api_url)
    if not base:
        raise ValueError("易支付接口地址未配置")
    sg = build_sign_string(
        money=money,
        name=name,
        notify_url=notify_url,
        out_trade_no=out_trade_no,
        pid=str(pid),
        return_url=return_url,
        sitename=sitename,
        pay_type=pay_type,
    )
    sign_val = calc_sign(sg, key)
    url = f"{base}/submit.php?{sg}&sign={sign_val}&sign_type=MD5"
    try:
        return _http_post(url)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"无法连接易支付接口: {exc}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"无法连接易支付接口: {exc}") from exc


def mapi(
    api_url: str,
    *,
    money: str,
    name: str,
    notify_url: str,
    out_trade_no: str,
    pay_type: str,
    pid: str,
    return_url: str,
    sitename: str,
    key: str,
) -> dict[str, Any]:
    """API 接口支付：POST mapi.php（官方文档，SDK 未包含）。"""
    base = normalize_base_url(api_url)
    if not base:
        raise ValueError("易支付接口地址未配置")
    fields = build_signed_fields(
        money=money,
        name=name,
        notify_url=notify_url,
        out_trade_no=out_trade_no,
        pid=str(pid),
        return_url=return_url,
        sitename=sitename,
        pay_type=pay_type,
        key=key,
    )
    try:
        body = _http_post(f"{base}/mapi.php", fields)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"无法连接易支付接口: {exc}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"易支付 mapi 请求失败: {exc}") from exc
    result = _parse_json(body)
    if result.get("code") not in SUCCESS_CODES:
        message = result.get("msg") or result.get("message") or "易支付下单失败"
        raise ValueError(str(message))
    return result


def act(api_url: str, pid: str, key: str, *, optional: bool = False) -> dict[str, Any] | None:
    """查询商户信息：GET api.php?act=query（官方 SDK act）。"""
    base = normalize_base_url(api_url)
    if not base:
        raise ValueError("易支付接口地址未配置")
    query = urllib.parse.urlencode({"act": "query", "pid": str(pid), "key": key})
    url = f"{base}/api.php?{query}"
    try:
        body = _http_get(url)
    except urllib.error.HTTPError as exc:
        if optional and exc.code in (404, 405):
            logger.info("ezfpy 商户查询接口不可用 (%s)，跳过: %s", exc.code, url)
            return None
        raise ValueError(f"无法连接易支付接口: {exc}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"无法连接易支付接口: {exc}") from exc
    body = body.strip()
    if not body:
        raise ValueError("易支付商户查询返回为空")
    if body.startswith("{"):
        result = _parse_json(body)
        if result.get("code") not in SUCCESS_CODES and str(result.get("status", "")).lower() not in ("success", "1"):
            message = result.get("msg") or result.get("message") or "商户查询失败"
            raise ValueError(str(message))
        return result
    return {"code": 200, "msg": "连接成功", "raw": body[:500]}


def _first_order_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data")
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            return data[0]
        return None
    if isinstance(data, dict):
        return data
    return None


def _normalize_order_record(record: dict[str, Any]) -> dict[str, Any]:
    status = record.get("status")
    if status is None:
        for field in ("state", "pay_status", "pay_state", "trade_state"):
            if field in record:
                status = record[field]
                break
    trade_status = record.get("trade_status")
    if not trade_status and status is not None:
        normalized = str(status).strip().lower()
        if normalized in {"1", "2", "paid", "success", "pay_success", "completed"}:
            trade_status = "TRADE_SUCCESS"
    return {
        "status": status,
        "trade_status": trade_status or "",
        "trade_no": str(
            record.get("trade_no")
            or record.get("order_id")
            or record.get("transaction_id")
            or ""
        ),
    }


def order(api_url: str, out_trade_no: str) -> dict[str, Any]:
    """查询单个订单：POST api/findorder（ezfpy 线上实际接口）。"""
    base = normalize_base_url(api_url)
    if not base:
        raise ValueError("易支付接口地址未配置")
    url = f"{base}/api/findorder"
    try:
        body = _http_post(url, {"order_no": out_trade_no, "type": "1"})
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 405):
            raise ValueError("网关未提供订单查询接口") from exc
        raise ValueError(f"无法连接易支付接口: {exc}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"订单查询失败: {exc}") from exc
    result = _parse_json(body)
    if result.get("code") not in SUCCESS_CODES:
        return {"status": "0", "trade_status": "", "trade_no": ""}
    record = _first_order_record(result)
    if not record:
        return {"status": "0", "trade_status": "", "trade_no": ""}
    return _normalize_order_record(record)
