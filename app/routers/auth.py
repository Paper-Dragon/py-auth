from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import encrypt_response_data, try_decrypt_heartbeat
from app.database import get_db
from app.models import Device, Product
from app.product_auth import evaluate_device_authorization, resolve_initial_authorization
from app.product_resolve import resolve_product_by_client_secret
from app.product_utils import (
    CLIENT_SOFTWARE_NAME_MISMATCH_DETAIL,
    client_software_name_matches_product,
)
from app.rate_limit import require_rate_limit
from app.schemas import DeviceAuthRequest, EncryptedRequest, EncryptedResponse
from app.ws_manager import device_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["授权"])


def _apply_trackable_updates(device: Device, request: DeviceAuthRequest) -> bool:
    changed = False
    if request.software_name is not None and request.software_name != device.software_name:
        device.software_name = request.software_name
        changed = True
    if request.device_info is not None and request.device_info != device.device_info:
        device.device_info = request.device_info
        changed = True
    return changed


def _sync_device(device: Device, request: DeviceAuthRequest, product: Product) -> None:
    changed = _apply_trackable_updates(device, request)
    if device.product_key != product.key:
        device.product_key = product.key
        changed = True
    if changed:
        device.updated_at = datetime.now()


def _get_or_create_device(
    request: DeviceAuthRequest,
    db: Session,
    product: Product,
) -> tuple[Device, bool]:
    device = db.query(Device).filter(Device.device_id == request.device_id).first()
    if device:
        _sync_device(device, request, product)
        return device, False

    device = Device(
        device_id=request.device_id,
        product_key=product.key,
        software_name=request.software_name,
        device_info=request.device_info,
        is_authorized=resolve_initial_authorization(product),
    )
    db.add(device)
    try:
        db.flush()
        return device, True
    except IntegrityError:
        db.rollback()
        device = db.query(Device).filter(Device.device_id == request.device_id).first()
        if device is None:
            raise
        _sync_device(device, request, product)
        return device, False


def _process_device(
    request: DeviceAuthRequest,
    db: Session,
    *,
    product: Product,
) -> tuple[Device, bool, str, str | None]:
    device, created = _get_or_create_device(request, db, product)
    evaluation = evaluate_device_authorization(db, device, product=product)
    if device.is_authorized != evaluation.authorized:
        device.is_authorized = evaluation.authorized
        device.updated_at = datetime.now()
    device.last_check = datetime.now()
    db.commit()
    db.refresh(device)
    return device, created, evaluation.message, evaluation.plan


@router.post("/heartbeat", response_model=EncryptedResponse)
async def heartbeat(
    request: EncryptedRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_rate_limit("heartbeat")),
):
    """设备心跳：client_secret 解析产品 UUID 并执行授权策略。"""
    data, client_secret = try_decrypt_heartbeat(db, request.encrypted_data)
    if not data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="解密失败，无法验证设备")

    product = resolve_product_by_client_secret(db, client_secret)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无效的 client_secret，无法解析产品 UUID",
        )

    auth_request = DeviceAuthRequest(**data)
    if not client_software_name_matches_product(product, auth_request.software_name):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=CLIENT_SOFTWARE_NAME_MISMATCH_DETAIL,
        )

    device, created, message, plan = _process_device(auth_request, db, product=product)

    await device_ws_manager.broadcast({
        "type": "devices_changed",
        "action": "created" if created else "heartbeat",
        "device_id": device.device_id,
    })

    response_data: dict = {
        "authorized": device.is_authorized,
        "message": message,
    }
    if plan:
        response_data["plan"] = plan

    encrypted = encrypt_response_data(response_data, client_secret)
    if not encrypted:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="加密响应失败")

    return EncryptedResponse(encrypted_data=encrypted)
