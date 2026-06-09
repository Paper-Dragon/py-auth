import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth import get_user_by_username, verify_token
from app.database import session_scope
from app.device_query import list_devices_payload
from app.services import device_service
from app.ws_manager import device_ws_manager

router = APIRouter(tags=["管理"])


def _authenticate(token: str) -> str | None:
    """校验 WebSocket token，返回管理员用户名或 None。"""
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None
    with session_scope() as db:
        user = get_user_by_username(db, username)
        if user and user.is_active and user.is_admin:
            return user.username
    return None


async def _send_device_list(websocket: WebSocket, *, request_id=None, **list_kwargs) -> None:
    with session_scope() as db:
        result = list_devices_payload(db, **list_kwargs)
    payload = {
        "type": "devices_list",
        "total": result["total"],
        "summary": result["summary"],
        "devices": result["devices"],
    }
    if request_id is not None:
        payload["request_id"] = request_id
    await websocket.send_json(payload)


async def _handle_get_devices(websocket: WebSocket, data: dict) -> None:
    await _send_device_list(
        websocket,
        request_id=data.get("request_id"),
        page=max(1, int(data.get("page", 1))),
        page_size=max(1, min(200, int(data.get("page_size", 50)))),
        sort_by=data.get("sort_by", "updated_at"),
        sort_order=data.get("sort_order", "desc"),
        product_key=data.get("product_key") or None,
        keyword=data.get("keyword") or None,
        auth_status=data.get("auth_status") or None,
    )


async def _handle_update_device(websocket: WebSocket, data: dict, actor: str) -> None:
    request_id = data.get("request_id")
    try:
        with session_scope() as db:
            device = device_service.update_device(
                db,
                actor=actor,
                device_id=data.get("device_id", ""),
                raw_update=data.get("data") or {},
            )
        await websocket.send_json({
            "type": "device_updated",
            "request_id": request_id,
            "device": device,
        })
        await device_ws_manager.broadcast({
            "type": "devices_changed",
            "action": "updated",
            "device_id": device["device_id"],
        })
    except Exception as exc:
        await websocket.send_json({
            "type": "error",
            "request_id": request_id,
            "message": str(exc) or "更新失败",
        })


async def _handle_delete_device(websocket: WebSocket, data: dict, actor: str) -> None:
    request_id = data.get("request_id")
    try:
        with session_scope() as db:
            device_id = device_service.delete_device(
                db, actor=actor, device_id=data.get("device_id", "")
            )
        await websocket.send_json({
            "type": "device_deleted",
            "request_id": request_id,
            "device_id": device_id,
        })
        await device_ws_manager.broadcast({
            "type": "devices_changed",
            "action": "deleted",
            "device_id": device_id,
        })
    except Exception as exc:
        await websocket.send_json({
            "type": "error",
            "request_id": request_id,
            "message": str(exc) or "删除失败",
        })


async def _handle_delete_devices(websocket: WebSocket, data: dict, actor: str) -> None:
    request_id = data.get("request_id")
    try:
        with session_scope() as db:
            ids = device_service.delete_devices(
                db, actor=actor, raw_ids=data.get("device_ids")
            )
        await websocket.send_json({
            "type": "devices_deleted",
            "request_id": request_id,
            "device_ids": ids,
            "deleted_count": len(ids),
        })
        await device_ws_manager.broadcast({
            "type": "devices_changed",
            "action": "deleted",
            "device_ids": ids,
        })
    except Exception as exc:
        await websocket.send_json({
            "type": "error",
            "request_id": request_id,
            "message": str(exc) or "批量删除失败",
        })


@router.websocket("/ws")
async def device_events(websocket: WebSocket):
    actor = _authenticate(websocket.query_params.get("token", ""))
    if not actor:
        await websocket.close(code=4401, reason="unauthorized")
        return

    await device_ws_manager.connect(websocket)
    await websocket.send_json({"type": "connected"})
    await _send_device_list(websocket, page=1, page_size=50)

    handlers = {
        "get_devices": lambda data: _handle_get_devices(websocket, data),
        "update_device": lambda data: _handle_update_device(websocket, data, actor),
        "delete_device": lambda data: _handle_delete_device(websocket, data, actor),
        "delete_devices": lambda data: _handle_delete_devices(websocket, data, actor),
    }

    try:
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
            except Exception:
                continue
            handler = handlers.get(data.get("type"))
            if handler:
                await handler(data)
    except WebSocketDisconnect:
        device_ws_manager.disconnect(websocket)
    except Exception:
        device_ws_manager.disconnect(websocket)
