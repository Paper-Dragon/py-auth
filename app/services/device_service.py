"""设备管理业务逻辑（供 WebSocket 路由调用）。

负责设备的更新/删除与审计日志记录，业务错误以 ValueError 抛出，
由调用方转换为对应的协议响应。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.audit import add_operation_log
from app.device_query import serialize_device
from app.models import Device, Product
from app.product_resolve import build_product_key_map

MAX_BULK_DELETE = 200

_UPDATABLE_FIELDS = ("remark", "is_authorized", "is_banned", "manual_plan")

MAX_MANUAL_PLAN_LEN = 64


def _extract_allowed_updates(raw_update: Any) -> dict[str, Any]:
    if not isinstance(raw_update, dict):
        raise ValueError("data 格式错误")
    allowed: dict[str, Any] = {}
    for field in _UPDATABLE_FIELDS:
        if field in raw_update:
            allowed[field] = raw_update.get(field)
    if not allowed:
        raise ValueError("缺少可更新字段")
    return allowed


def update_device(
    db: Session,
    *,
    actor: str,
    device_id: str,
    raw_update: Any,
) -> dict:
    """更新设备的备注/授权状态，返回序列化后的设备数据。"""
    device_id = str(device_id or "").strip()
    if not device_id:
        raise ValueError("缺少 device_id")

    allowed = _extract_allowed_updates(raw_update)

    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise ValueError("设备不存在")

    original_created_at = device.created_at
    if "remark" in allowed:
        device.remark = allowed.get("remark")
    if "is_authorized" in allowed:
        device.is_authorized = bool(allowed.get("is_authorized"))
    if "is_banned" in allowed:
        device.is_banned = bool(allowed.get("is_banned"))
    if "manual_plan" in allowed:
        raw_plan = allowed.get("manual_plan")
        plan = str(raw_plan).strip() if raw_plan is not None else ""
        if len(plan) > MAX_MANUAL_PLAN_LEN:
            raise ValueError(f"套餐档位不能超过 {MAX_MANUAL_PLAN_LEN} 个字符")
        device.manual_plan = plan or None
    device.updated_at = datetime.now()
    device.created_at = original_created_at

    add_operation_log(
        db,
        username=actor,
        action="update_device",
        target_type="device",
        target_id=device.device_id,
        detail=allowed,
    )
    db.commit()
    db.refresh(device)

    products = db.query(Product).all()
    product_map = build_product_key_map(products)
    return serialize_device(device, product_map, db)


def delete_device(db: Session, *, actor: str, device_id: str) -> str:
    """删除单台设备，返回被删除的 device_id。"""
    device_id = str(device_id or "").strip()
    if not device_id:
        raise ValueError("缺少 device_id")

    deleted_count = db.query(Device).filter(Device.device_id == device_id).delete()
    if deleted_count == 0:
        raise ValueError("设备不存在")

    add_operation_log(
        db,
        username=actor,
        action="delete_device",
        target_type="device",
        target_id=device_id,
        detail=None,
    )
    db.commit()
    return device_id


def _normalize_device_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        raise ValueError("device_ids 须为非空数组")
    device_ids: list[str] = []
    seen: set[str] = set()
    for item in raw:
        value = str(item).strip()
        if value and value not in seen:
            seen.add(value)
            device_ids.append(value)
    if not device_ids:
        raise ValueError("device_ids 须为非空数组")
    if len(device_ids) > MAX_BULK_DELETE:
        raise ValueError(f"一次最多删除 {MAX_BULK_DELETE} 台设备")
    return device_ids


def delete_devices(db: Session, *, actor: str, raw_ids: Any) -> list[str]:
    """批量删除设备，返回实际删除的 device_id 列表。"""
    device_ids = _normalize_device_ids(raw_ids)

    existing = (
        db.query(Device.device_id)
        .filter(Device.device_id.in_(device_ids))
        .all()
    )
    ids = [row[0] for row in existing]
    if not ids:
        raise ValueError("没有可删除的设备")

    db.query(Device).filter(Device.device_id.in_(ids)).delete(synchronize_session=False)
    for device_id in ids:
        add_operation_log(
            db,
            username=actor,
            action="delete_device",
            target_type="device",
            target_id=device_id,
            detail=None,
        )
    db.commit()
    return ids
