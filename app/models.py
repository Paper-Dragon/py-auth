from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.database import Base

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(255), unique=True, index=True, nullable=False)
    software_name = Column(String(255), nullable=True)  # 软件名
    device_info = Column(JSON, nullable=True)  # 设备信息（JSON格式，包含hostname等）
    remark = Column(Text, nullable=True)  # 备注
    is_authorized = Column(Boolean, default=True, nullable=False)  # 默认授权
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_check = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Device(id={self.id}, device_id={self.device_id}, authorized={self.is_authorized})>"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, is_admin={self.is_admin})>"

