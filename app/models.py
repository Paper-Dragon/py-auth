from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from datetime import datetime
from app.database import Base

AUTH_MODE_OPEN = "open"
AUTH_MODE_MANUAL = "manual"
AUTH_MODE_PAID = "paid"

AUTH_MODES = (
    AUTH_MODE_OPEN,
    AUTH_MODE_MANUAL,
    AUTH_MODE_PAID,
)

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(255), unique=True, index=True, nullable=False)
    product_key = Column(String(64), nullable=True, index=True)
    software_name = Column(String(255), nullable=True)       
    device_info = Column(JSON, nullable=True)                            
    remark = Column(Text, nullable=True)      
    is_authorized = Column(Boolean, default=True, nullable=False)        
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)
    last_check = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Device(id={self.id}, device_id={self.device_id}, authorized={self.is_authorized})>"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, is_admin={self.is_admin})>"


class Config(Base):
    __tablename__ = "config"
    
    key = Column(String(255), primary_key=True, index=True)
    value = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<Config(key={self.key}, value={self.value})>"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    out_trade_no = Column(String(64), unique=True, index=True, nullable=False)
    trade_no = Column(String(64), nullable=True, index=True)
    device_id = Column(String(255), nullable=False, index=True)
    product_key = Column(String(64), nullable=False, index=True)
    product_name = Column(String(255), nullable=True)
    plan = Column(String(64), nullable=True)
    money = Column(String(16), nullable=False)
    pay_type = Column(String(32), nullable=False)
    status = Column(String(32), default="pending", nullable=False, index=True)
    param = Column(String(255), nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<Order(id={self.id}, out_trade_no={self.out_trade_no}, status={self.status})>"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, index=True, nullable=False)
    software_name = Column(String(64), unique=True, index=True, nullable=True)
    client_secret = Column(String(128), nullable=True)
    display_name = Column(String(255), nullable=False)
    auth_mode = Column(String(32), default=AUTH_MODE_OPEN, nullable=False)
    config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<Product(id={self.id}, key={self.key}, auth_mode={self.auth_mode})>"


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=False, index=True)
    target_id = Column(String(255), nullable=True, index=True)
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now, index=True)

    def __repr__(self):
        return (
            f"<OperationLog(id={self.id}, username={self.username}, "
            f"action={self.action}, target_type={self.target_type}, target_id={self.target_id})>"
        )
