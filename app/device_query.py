from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Device, Product
from app.product_resolve import build_product_key_map
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
        query = query.filter(
            (Device.device_id.like(kw))
            | (Device.remark.like(kw))
            | (Device.software_name.like(kw))
            | (Device.product_key.like(kw))
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


def serialize_device(device: Device, product_map: dict[str, Product]) -> dict:
    data = DeviceResponse.model_validate(device).model_dump(mode="json")
    bound_key = (device.product_key or "").strip()
    product = product_map.get(bound_key) if bound_key else None
    data["product_known"] = product is not None and not product.is_default
    data["product_display_name"] = product.display_name if product else None
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
            serialize_device(device, product_map) for device in devices
        ],
    }
