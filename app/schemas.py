from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any

class EncryptedRequest(BaseModel):
    """加密的请求数据（device_id、software_name 等在加密载荷内；产品 UUID 由 client_secret 解析，software_name 须与该产品一致）"""
    encrypted_data: str

class DeviceAuthRequest(BaseModel):
    """设备授权请求（检查/注册共用）"""
    device_id: str
    software_name: Optional[str] = None       
    device_info: Optional[Dict[str, Any]] = None                                                                                             

class DeviceResponse(BaseModel):
    id: int
    device_id: str
    product_key: Optional[str] = None
    software_name: Optional[str] = None       
    device_info: Optional[Dict[str, Any]] = None                                      
    remark: Optional[str]
    is_authorized: bool
    product_display_name: Optional[str] = None
    product_known: bool = False
    product_auth_mode: Optional[str] = None
    plan: Optional[str] = None
    plan_label: Optional[str] = None
    plan_hint: Optional[str] = None
    plan_tag: Optional[str] = None
    auth_message: Optional[str] = None
    created_at: datetime = Field(description="首次注册：设备首次接入后不变")
    updated_at: Optional[datetime] = Field(
        default=None,
        description="最近更新：授权、备注或设备信息变更时刷新",
    )
    last_check: Optional[datetime] = Field(
        default=None,
        description="最近活跃：最后一次心跳或授权校验时刷新",
    )

    class Config:
        from_attributes = True


class DeviceListSummary(BaseModel):
    total: int = 0
    authorized: int = 0
    unauthorized: int = 0


class ProductOptionResponse(BaseModel):
    key: str
    software_name: str = ""
    display_name: str
    is_active: bool = True

class EncryptedResponse(BaseModel):
    """加密的响应数据"""
    encrypted_data: str                    

class UserCreate(BaseModel):
    username: str
    password: str
    is_admin: Optional[bool] = False
    is_active: Optional[bool] = True

class UserUpdate(BaseModel):
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    is_admin: bool

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ConfigUpdate(BaseModel):
    configs: Dict[str, Any]


class OperationLogResponse(BaseModel):
    id: int
    username: str
    action: str
    target_type: str
    target_id: Optional[str]
    detail: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class OperationLogListResponse(BaseModel):
    total: int
    logs: list[OperationLogResponse]


class ProductCreate(BaseModel):
    key: Optional[str] = None
    software_name: str = Field(description="客户端 SDK 的 software_name，软件名称，非内部 UUID")
    display_name: Optional[str] = None
    auth_mode: str = "open"
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = True


class ProductUpdate(BaseModel):
    software_name: Optional[str] = None
    display_name: Optional[str] = None
    auth_mode: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class EpayConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    api_url: Optional[str] = None
    pid: Optional[str] = None
    key: Optional[str] = None
    notify_url: Optional[str] = None
    return_url: Optional[str] = None
    order_mode: Optional[str] = None
    sitename: Optional[str] = None
    enabled_channels: Optional[list[str]] = None


class EpayConfigResponse(BaseModel):
    enabled: bool
    api_url: str
    pid: str
    key: str
    key_configured: bool
    notify_url: str
    return_url: str
    order_mode: str = "mapi"
    sitename: str = ""
    enabled_channels: list[str] = Field(default_factory=lambda: ["alipay", "wxpay", "qqpay"])
    resolved_notify_url: str = ""
    resolved_return_url: str = ""
    resolved_pay_url: str = ""


class PaymentChannelsResponse(BaseModel):
    enabled: bool
    channels: list[str] = Field(default_factory=list)


class EpayTestConnectionRequest(BaseModel):
    pay_type: str = Field(default="alipay", description="alipay、wxpay 或 qqpay")


class EpayTestConnectionResponse(BaseModel):
    success: bool
    message: str
    detail: Optional[Dict[str, Any]] = None


class EpayTestPayRequest(BaseModel):
    pay_type: str = Field(default="alipay", description="alipay、wxpay 或 qqpay")
    money: str = Field(default="0.01", description="测试金额，默认 0.01 元")


class PaymentDeviceContextResponse(BaseModel):
    device_id: str
    software_name: Optional[str] = None
    display_name: Optional[str] = None
    auth_mode: Optional[str] = None
    plan: Optional[str] = None
    plan_detail: Optional[str] = None
    price: Optional[str] = None
    pay_type: Optional[str] = None
    can_pay: bool = False
    message: str = ""


class PaymentOrderCreate(BaseModel):
    device_id: str


class PaymentOrderPublicResponse(BaseModel):
    """支付方仅凭订单号 + 设备 ID 可查询的有限字段，避免泄露他人订单信息。"""
    out_trade_no: str
    status: str
    paid_at: Optional[datetime] = None
    is_test: bool = False


class PaymentOrderResponse(BaseModel):
    id: int
    out_trade_no: str
    trade_no: Optional[str] = None
    device_id: str
    product_name: Optional[str] = None
    plan: Optional[str] = None
    money: str
    pay_type: str
    status: str
    is_test: bool = False
    pay_mode: str = "redirect"
    pay_url: Optional[str] = None
    submit_action: Optional[str] = None
    form_fields: Optional[Dict[str, str]] = None
    qr_content: Optional[str] = None
    qr_image: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaymentOrderSummary(BaseModel):
    total: int = 0
    pending: int = 0
    paid: int = 0
    test: int = 0


class PaymentOrderListResponse(BaseModel):
    total: int
    orders: list[PaymentOrderResponse]
    summary: PaymentOrderSummary = Field(default_factory=PaymentOrderSummary)


class ProductResponse(BaseModel):
    id: int
    key: str
    software_name: str = ""
    display_name: str
    auth_mode: str
    config: Optional[Dict[str, Any]] = None
    is_active: bool
    is_default: bool = False
    device_count: int = 0
    client_secret: str = ""
    client_secret_configured: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
