from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Device, User
from app.schemas import DeviceResponse, DeviceUpdate
from app.auth import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["管理"])


def get_device_or_404(device_id: str, db: Session) -> Device:
    """获取设备，不存在则抛出404异常"""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device

@router.get("/devices")
async def get_devices(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有设备列表（需要登录），按更新时间降序排列"""
    total = db.query(Device).count()
    devices = db.query(Device).order_by(Device.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "devices": [DeviceResponse.model_validate(d) for d in devices]}

@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个设备信息（需要登录）"""
    return get_device_or_404(device_id, db)

@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    device_update: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新设备信息（需要登录）"""
    device = get_device_or_404(device_id, db)
    
    update_data = device_update.model_dump(exclude_unset=True)
    
    if update_data:
        db.query(Device).filter(Device.device_id == device_id).update(update_data, synchronize_session=False)
        db.commit()
        db.refresh(device)
    
    return device

@router.delete("/devices/{device_id}")
async def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除设备（需要登录）"""
    db.query(Device).filter(Device.device_id == device_id).delete()
    db.commit()
    return {"message": "已删除"}

