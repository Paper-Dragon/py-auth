import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth import get_user_by_username, verify_token
from app.database import SessionLocal
from app.device_query import list_devices_payload, serialize_device
from app.models import Product
from app.product_resolve import build_product_key_map
from app.models import Device, OperationLog
from app.ws_manager import device_ws_manager

router = APIRouter(tags=["管理"])


@router.websocket("/ws")
async def device_events(websocket: WebSocket):
             
    token = websocket.query_params.get("token", "")
    actor = None
    if token:
        payload = verify_token(token)
        if payload:
            username = payload.get("sub")
            if username:
                db = SessionLocal()
                try:
                    user = get_user_by_username(db, username)
                    if user and user.is_active and user.is_admin:
                        actor = user.username
                finally:
                    db.close()
    
    if not actor:
        await websocket.close(code=4401, reason="unauthorized")
        return

                 
    await device_ws_manager.connect(websocket)
    await websocket.send_json({"type": "connected"})
    
                         
    db = SessionLocal()
    try:
        initial = list_devices_payload(db, page=1, page_size=50)
        initial_payload = {
            "type": "devices_list",
            "total": initial["total"],
            "summary": initial["summary"],
            "devices": initial["devices"],
        }
        await websocket.send_json(initial_payload)
    finally:
        db.close()
    
          
    try:
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
            except Exception:
                continue

                             
            if data.get("type") == "get_devices":
                request_id = data.get("request_id")
                page = max(1, int(data.get("page", 1)))
                page_size = max(1, min(200, int(data.get("page_size", 50))))
                sort_by = data.get("sort_by", "updated_at")
                sort_order = data.get("sort_order", "desc")
                product_key = data.get("product_key") or None
                keyword = data.get("keyword") or None
                auth_status = data.get("auth_status") or None

                db = SessionLocal()
                try:
                    result = list_devices_payload(
                        db,
                        page=page,
                        page_size=page_size,
                        sort_by=sort_by,
                        sort_order=sort_order,
                        product_key=product_key,
                        keyword=keyword,
                        auth_status=auth_status,
                    )
                    payload = {
                        "type": "devices_list",
                        "request_id": request_id,
                        "total": result["total"],
                        "summary": result["summary"],
                        "devices": result["devices"],
                    }
                    await websocket.send_json(payload)
                finally:
                    db.close()
                continue

                  
            if data.get("type") == "update_device":
                request_id = data.get("request_id")
                try:
                    device_id = str(data.get("device_id", "")).strip()
                    if not device_id:
                        raise ValueError("缺少 device_id")
                    
                    raw_update = data.get("data") or {}
                    if not isinstance(raw_update, dict):
                        raise ValueError("data 格式错误")

                    allowed = {}
                    if "remark" in raw_update:
                        allowed["remark"] = raw_update.get("remark")
                    if "is_authorized" in raw_update:
                        allowed["is_authorized"] = raw_update.get("is_authorized")
                    if not allowed:
                        raise ValueError("缺少可更新字段")

                    db = SessionLocal()
                    try:
                        device = db.query(Device).filter(Device.device_id == device_id).first()
                        if not device:
                            raise ValueError("设备不存在")
                        
                        original_created_at = device.created_at

                        if "remark" in allowed:
                            device.remark = allowed.get("remark")
                        if "is_authorized" in allowed:
                            device.is_authorized = bool(allowed.get("is_authorized"))

                        device.updated_at = datetime.now()
                        device.created_at = original_created_at
                        
                        db.add(OperationLog(
                            username=actor,
                            action="update_device",
                            target_type="device",
                            target_id=device.device_id,
                            detail=allowed
                        ))
                        db.commit()
                        db.refresh(device)
                        products = db.query(Product).all()
                        product_map = build_product_key_map(products)

                        payload = {
                            "type": "device_updated",
                            "request_id": request_id,
                            "device": serialize_device(device, product_map),
                        }
                        await websocket.send_json(payload)
                        await device_ws_manager.broadcast({
                            "type": "devices_changed",
                            "action": "updated",
                            "device_id": device_id
                        })
                    finally:
                        db.close()
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "request_id": request_id,
                        "message": str(e) or "更新失败"
                    })
                continue

                  
            if data.get("type") == "delete_device":
                request_id = data.get("request_id")
                try:
                    device_id = str(data.get("device_id", "")).strip()
                    if not device_id:
                        raise ValueError("缺少 device_id")
                    
                    db = SessionLocal()
                    try:
                        deleted_count = db.query(Device).filter(Device.device_id == device_id).delete()
                        if deleted_count == 0:
                            raise ValueError("设备不存在")
                        
                        db.add(OperationLog(
                            username=actor,
                            action="delete_device",
                            target_type="device",
                            target_id=device_id,
                            detail=None
                        ))
                        db.commit()
                        
                        payload = {
                            "type": "device_deleted",
                            "request_id": request_id,
                            "device_id": device_id
                        }
                        await websocket.send_json(payload)
                        await device_ws_manager.broadcast({
                            "type": "devices_changed",
                            "action": "deleted",
                            "device_id": device_id
                        })
                    finally:
                        db.close()
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "request_id": request_id,
                        "message": str(e) or "删除失败"
                    })
                continue

            if data.get("type") == "delete_devices":
                request_id = data.get("request_id")
                try:
                    raw = data.get("device_ids")
                    if not isinstance(raw, list):
                        raise ValueError("device_ids 须为非空数组")
                    device_ids: list[str] = []
                    seen: set[str] = set()
                    for x in raw:
                        s = str(x).strip()
                        if s and s not in seen:
                            seen.add(s)
                            device_ids.append(s)
                    if not device_ids:
                        raise ValueError("device_ids 须为非空数组")
                    if len(device_ids) > 200:
                        raise ValueError("一次最多删除 200 台设备")

                    db = SessionLocal()
                    try:
                        existing = (
                            db.query(Device.device_id)
                            .filter(Device.device_id.in_(device_ids))
                            .all()
                        )
                        ids = [r[0] for r in existing]
                        if not ids:
                            raise ValueError("没有可删除的设备")
                        db.query(Device).filter(Device.device_id.in_(ids)).delete(
                            synchronize_session=False
                        )
                        for did in ids:
                            db.add(
                                OperationLog(
                                    username=actor,
                                    action="delete_device",
                                    target_type="device",
                                    target_id=did,
                                    detail=None,
                                )
                            )
                        db.commit()
                        payload = {
                            "type": "devices_deleted",
                            "request_id": request_id,
                            "device_ids": ids,
                            "deleted_count": len(ids),
                        }
                        await websocket.send_json(payload)
                        await device_ws_manager.broadcast(
                            {
                                "type": "devices_changed",
                                "action": "deleted",
                                "device_ids": ids,
                            }
                        )
                    finally:
                        db.close()
                except Exception as e:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "request_id": request_id,
                            "message": str(e) or "批量删除失败",
                        }
                    )
                continue
    except WebSocketDisconnect:
        device_ws_manager.disconnect(websocket)
    except Exception:
        device_ws_manager.disconnect(websocket)
