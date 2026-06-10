import os
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.coerce import coerce_boolish
from app.epay import EPAY_PAY_TYPES, normalize_epay_api_url
from app.models import Config

EPAY_CONFIG_KEY = "epay_config"
ALL_EPAY_CHANNELS: tuple[str, ...] = tuple(sorted(EPAY_PAY_TYPES))

DEFAULT_EPAY_CONFIG: dict[str, Any] = {
    "enabled": False,
    "api_url": "",
    "pid": "",
    "key": "",
    "notify_url": "",
    "return_url": "",
    "order_mode": "mapi",
    "sitename": "",
    "enabled_channels": list(ALL_EPAY_CHANNELS),
}

MASKED_KEY_PLACEHOLDER = "********"


def normalize_enabled_channels(channels: Any) -> list[str]:
    if channels is None:
        return list(ALL_EPAY_CHANNELS)
    if not isinstance(channels, list):
        return list(ALL_EPAY_CHANNELS)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in channels:
        key = str(item or "").strip().lower()
        if key in EPAY_PAY_TYPES and key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def get_enabled_channels(config: dict[str, Any]) -> list[str]:
    return normalize_enabled_channels(config.get("enabled_channels"))


def ensure_pay_type_enabled(config: dict[str, Any], pay_type: str) -> str:
    normalized = str(pay_type or "").strip().lower()
    if normalized not in EPAY_PAY_TYPES:
        raise ValueError("pay_type 仅支持 alipay、wxpay 或 qqpay")
    enabled = get_enabled_channels(config)
    if normalized not in enabled:
        labels = {"alipay": "支付宝", "wxpay": "微信", "qqpay": "QQ 钱包"}
        raise ValueError(f"支付方式「{labels.get(normalized, normalized)}」未开通")
    return normalized


def load_epay_config(db: Session) -> dict[str, Any]:
    row = db.query(Config).filter(Config.key == EPAY_CONFIG_KEY).first()
    config = deepcopy(DEFAULT_EPAY_CONFIG)
    if row and isinstance(row.value, dict):
        config.update(row.value)

    if not config.get("api_url"):
        config["api_url"] = os.getenv("EPAY_API_URL", "").strip()
    if not config.get("pid"):
        config["pid"] = os.getenv("EPAY_PID", "").strip()
    if not config.get("key"):
        config["key"] = os.getenv("EPAY_KEY", "").strip()
    if not config.get("notify_url"):
        config["notify_url"] = os.getenv("EPAY_NOTIFY_URL", "").strip()
    if not config.get("return_url"):
        config["return_url"] = os.getenv("EPAY_RETURN_URL", "").strip()

    config["enabled"] = coerce_boolish(config.get("enabled"), if_none=False)
    config["enabled_channels"] = normalize_enabled_channels(config.get("enabled_channels"))
    config["api_url"] = normalize_epay_api_url(str(config.get("api_url") or ""))
    return config


def save_epay_config(db: Session, updates: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    current = deepcopy(existing or DEFAULT_EPAY_CONFIG)
    row = db.query(Config).filter(Config.key == EPAY_CONFIG_KEY).first()
    if row and isinstance(row.value, dict):
        current.update(row.value)

    for field in ("enabled", "api_url", "pid", "notify_url", "return_url", "order_mode", "sitename"):
        if field in updates and updates[field] is not None:
            current[field] = updates[field]

    if "enabled_channels" in updates and updates["enabled_channels"] is not None:
        current["enabled_channels"] = normalize_enabled_channels(updates["enabled_channels"])

    if "key" in updates:
        new_key = str(updates["key"] or "").strip()
        if new_key and new_key != MASKED_KEY_PLACEHOLDER:
            current["key"] = new_key

    current["enabled"] = coerce_boolish(current.get("enabled"), if_none=False)
    current["api_url"] = normalize_epay_api_url(str(current.get("api_url", "")))
    current["pid"] = str(current.get("pid", "")).strip()
    current["notify_url"] = str(current.get("notify_url", "")).strip()
    current["return_url"] = str(current.get("return_url", "")).strip()
    order_mode = str(current.get("order_mode", "mapi")).strip() or "mapi"
    current["order_mode"] = order_mode if order_mode in ("mapi", "submit") else "mapi"
    current["sitename"] = str(current.get("sitename", "")).strip()
    current["enabled_channels"] = normalize_enabled_channels(current.get("enabled_channels"))

    if coerce_boolish(current.get("enabled"), if_none=False) and not current["enabled_channels"]:
        raise ValueError("启用易支付时须至少开通一种支付渠道")

    if row:
        row.value = current
    else:
        db.add(Config(key=EPAY_CONFIG_KEY, value=current))
    return current


def _origin_from_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def resolve_configured_public_base(config: dict[str, Any]) -> str:
    """仅使用显式配置（环境变量或完整跳转 URL），不含请求 Host 回退。"""
    return_url = str(config.get("return_url") or "").strip()
    for candidate in (
        os.getenv("PUBLIC_BASE_URL", "").strip(),
        _origin_from_url(return_url),
    ):
        if candidate:
            return candidate.rstrip("/")
    return ""


def resolve_public_base_url(config: dict[str, Any], fallback: str | None = None) -> str:
    configured = resolve_configured_public_base(config)
    if configured:
        return configured
    for candidate in (
        _origin_from_url(fallback or ""),
        (fallback or "").strip().rstrip("/"),
    ):
        if candidate:
            return candidate.rstrip("/")
    return ""


def resolve_notify_url(config: dict[str, Any], fallback_base: str | None = None) -> str:
    explicit = str(config.get("notify_url") or "").strip()
    if explicit:
        return explicit
    base = resolve_public_base_url(config, fallback_base)
    if not base:
        return ""
    return f"{base}/api/payment/epay/notify"


def resolve_return_url(config: dict[str, Any], fallback_base: str | None = None) -> str:
    explicit = str(config.get("return_url") or "").strip()
    if explicit:
        return explicit
    base = resolve_public_base_url(config, fallback_base)
    if not base:
        return ""
    return f"{base}/pay/result"


def resolve_pay_url(
    config: dict[str, Any],
    fallback_base: str | None = None,
    *,
    configured_only: bool = False,
) -> str:
    base = resolve_configured_public_base(config)
    if not base and not configured_only:
        base = resolve_public_base_url(config, fallback_base)
    if not base:
        return ""
    return f"{base}/pay"


def ensure_epay_credentials(
    config: dict[str, Any],
    fallback_base: str | None = None,
    *,
    require_enabled: bool = True,
    require_callbacks: bool = True,
) -> dict[str, str]:
    if require_enabled and not coerce_boolish(config.get("enabled"), if_none=False):
        raise ValueError("易支付尚未启用")
    api_url = normalize_epay_api_url(str(config.get("api_url") or ""))
    pid = str(config.get("pid") or "").strip()
    merchant_key = str(config.get("key") or "").strip()
    if not api_url or not pid or not merchant_key:
        raise ValueError("易支付配置不完整，请填写接口地址、商户 ID 和密钥")

    notify_url = resolve_notify_url(config, fallback_base)
    return_url = resolve_return_url(config, fallback_base)
    if require_callbacks and (not notify_url or not return_url):
        raise ValueError("无法生成回调地址，请配置 PUBLIC_BASE_URL 或手动填写 notify/return URL")

    return {
        "api_url": api_url,
        "pid": pid,
        "key": merchant_key,
        "notify_url": notify_url,
        "return_url": return_url,
        "order_mode": str(config.get("order_mode", "mapi")).strip() or "mapi",
        "sitename": str(config.get("sitename", "")).strip(),
    }


def ensure_epay_ready(config: dict[str, Any], fallback_base: str | None = None) -> dict[str, str]:
    return ensure_epay_credentials(config, fallback_base, require_enabled=True, require_callbacks=True)
