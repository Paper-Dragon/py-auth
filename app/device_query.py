from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Device, Product
from app.product_auth import build_device_plan_display, evaluate_device_authorization
from app.product_resolve import build_product_key_map
from app.product_utils import display_software_name
from app.schemas import DeviceListSummary, DeviceResponse


def apply_device_filters(
    query,
    *,
    product_key: str | None = None,
    keyword: str | None = None,
    auth_status: str | None = None,
):
    if product_key:
        if product_key == "__none__":
            query = query.filter(
                (Device.product_key.is_(None)) | (Device.product_key == "")
            )
        else:
            query = query.filter(Device.product_key == product_key)

    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.outerjoin(Product, Device.product_key == Product.key)
        query = query.filter(
            or_(
                Device.device_id.like(kw),
                Device.remark.like(kw),
                Device.software_name.like(kw),
                Device.product_key.like(kw),
                Product.display_name.like(kw),
                Product.software_name.like(kw),
            )
        )

    if auth_status == "authorized":
        query = query.filter(Device.is_authorized.is_(True))
    elif auth_status == "unauthorized":
        query = query.filter(Device.is_authorized.is_(False))

    return query


def build_device_summary(query) -> DeviceListSummary:
    total = query.count()
    authorized = query.filter(Device.is_authorized.is_(True)).count()
    return DeviceListSummary(
        total=total,
        authorized=authorized,
        unauthorized=max(0, total - authorized),
    )


def _product_display_name(product: Product) -> str:
    if product.is_default:
        return display_software_name(product)
    return (product.display_name or display_software_name(product)).strip()


def serialize_device(
    device: Device,
    product_map: dict[str, Product],
    db: Session | None = None,
) -> dict:
    data = DeviceResponse.model_validate(device).model_dump(mode="json")
    bound_key = (device.product_key or "").strip()
    product = product_map.get(bound_key) if bound_key else None
    data["product_known"] = product is not None and not product.is_default
    if product:
        data["product_display_name"] = _product_display_name(product)
        data["product_auth_mode"] = product.auth_mode
    else:
        data["product_display_name"] = None
        data["product_auth_mode"] = None

    if db is not None:
        evaluation = evaluate_device_authorization(db, device, product=product)
        data["plan"] = evaluation.plan
        data["auth_message"] = evaluation.message
        plan_display = build_device_plan_display(db, device, product, evaluation)
        data.update(plan_display)
    return data


def list_devices_payload(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    product_key: str | None = None,
    keyword: str | None = None,
    auth_status: str | None = None,
) -> dict:
    query = db.query(Device)
    query = apply_device_filters(
        query,
        product_key=product_key,
        keyword=keyword,
        auth_status=auth_status,
    )

    summary = build_device_summary(query)

    sort_fields = {
        "created_at": Device.created_at,
        "updated_at": Device.updated_at,
        "last_check": Device.last_check,
        "device_id": Device.device_id,
        "software_name": Device.software_name,
        "is_authorized": Device.is_authorized,
    }
    sort_field = sort_fields.get(sort_by, Device.updated_at)
    query = (
        query.order_by(sort_field.asc())
        if sort_order.lower() == "asc"
        else query.order_by(sort_field.desc())
    )

    devices = query.offset((page - 1) * page_size).limit(page_size).all()
    products = db.query(Product).all()
    product_map = build_product_key_map(products)

    return {
        "total": summary.total,
        "summary": summary.model_dump(mode="json"),
        "devices": [
            serialize_device(device, product_map, db) for device in devices
        ],
    }
