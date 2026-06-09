"""产品配置与 client_secret 工具。"""
from __future__ import annotations

import re
import secrets
import uuid

from app.models import Product

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
LEGACY_PRODUCT_KEY_PATTERN = re.compile(r"^prod_[a-zA-Z0-9_-]+$")

DEFAULT_PRODUCT_SOFTWARE_NAME = "__default__"
DEFAULT_PRODUCT_DISPLAY_NAME = "默认产品"
LEGACY_DEFAULT_PRODUCT_DISPLAY_NAME = "未登记产品（默认）"
CLIENT_SOFTWARE_NAME_MISMATCH_DETAIL = "software_name 与 client_secret 不一致"


def generate_product_key() -> str:
    return str(uuid.uuid4())


def generate_client_secret() -> str:
    return f"sk_{secrets.token_hex(16)}"


def is_uuid(value: str) -> bool:
    return bool(UUID_PATTERN.match((value or "").strip()))


def is_reserved_software_name(name: str) -> bool:
    return (name or "").strip() == DEFAULT_PRODUCT_SOFTWARE_NAME


def validate_product_key(key: str) -> str:
    value = (key or "").strip()
    if is_uuid(value) or LEGACY_PRODUCT_KEY_PATTERN.match(value):
        return value
    raise ValueError("内部标识须为 UUID，或兼容旧版 prod_ 格式")


def plan_from_product(product: Product | None) -> str | None:
    if not product:
        return None
    config = product.config if isinstance(product.config, dict) else {}
    plan = str(config.get("plan_on_paid", "pro")).strip()
    return plan or "pro"


def software_name_for_product(product: Product | None, *, fallback: str = "") -> str:
    if product and (product.software_name or "").strip():
        return product.software_name.strip()
    return fallback


def display_software_name(product: Product) -> str:
    if product.is_default:
        name = (product.display_name or "").strip()
        if not name or name == LEGACY_DEFAULT_PRODUCT_DISPLAY_NAME:
            return DEFAULT_PRODUCT_DISPLAY_NAME
        return name
    return (product.software_name or product.display_name or "").strip()


def client_software_name_matches_product(
    product: Product, software_name: str | None
) -> bool:
    """校验心跳载荷中的 software_name 是否与 client_secret 所属产品一致。"""
    if product.is_default:
        return True
    expected = (product.software_name or "").strip()
    if not expected:
        return True
    return (software_name or "").strip() == expected


def client_secret_for_product(product: Product) -> str:
    """默认产品的 Client Secret 固定读取环境变量 CLIENT_SECRET。"""
    if product.is_default:
        from app.config import CLIENT_SECRET

        return (CLIENT_SECRET or "").strip()
    return (product.client_secret or "").strip()


def pay_type_from_product(product: Product | None) -> str:
    if not product:
        return "wxpay"
    config = product.config if isinstance(product.config, dict) else {}
    pay_type = str(config.get("pay_type", "wxpay")).strip().lower()
    return pay_type or "wxpay"
