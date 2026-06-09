"""产品查询：授权按 UUID（product.key），由 client_secret 解析。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import CLIENT_SECRET
from app.models import Device, Product
from app.product_utils import DEFAULT_PRODUCT_SOFTWARE_NAME


def get_default_product(db: Session) -> Product | None:
    return (
        db.query(Product)
        .filter(Product.is_default.is_(True))
        .order_by(Product.id.asc())
        .first()
    )


def resolve_product(db: Session, identifier: str | None) -> Product | None:
    """按 software_name 查产品（仅迁移/展示兼容）。"""
    value = (identifier or "").strip()
    if not value or value == DEFAULT_PRODUCT_SOFTWARE_NAME:
        return None
    product = db.query(Product).filter(Product.software_name == value).first()
    if product:
        return product
    return db.query(Product).filter(Product.key == value).first()


def resolve_product_by_client_secret(db: Session, client_secret: str | None) -> Product | None:
    """按 client_secret 查产品，得到授权策略对应的 UUID（product.key）。"""
    secret = (client_secret or "").strip()
    if not secret:
        return None
    global_secret = (CLIENT_SECRET or "").strip()
    if global_secret and secret == global_secret:
        return get_default_product(db)
    return db.query(Product).filter(Product.client_secret == secret).first()


def get_product_by_key(db: Session, product_key: str | None) -> Product | None:
    key = (product_key or "").strip()
    if not key:
        return None
    return db.query(Product).filter(Product.key == key).first()


def build_product_key_map(products: list[Product]) -> dict[str, Product]:
    return {product.key: product for product in products}


def count_devices_for_product(db: Session, product: Product) -> int:
    from sqlalchemy import func

    return (
        db.query(func.count(Device.id))
        .filter(Device.product_key == product.key)
        .scalar()
        or 0
    )


def count_devices_by_product(db: Session, products: list[Product]) -> dict[str, int]:
    return {product.key: count_devices_for_product(db, product) for product in products}
