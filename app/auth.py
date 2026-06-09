"""
用户认证相关工具
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Product, User
import os
import json
import base64
import logging
from cryptography.fernet import Fernet
import hashlib

logger = logging.getLogger(__name__)

    
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-12345678")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))          
                    
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")

_cipher_cache: dict[str, Fernet] = {}


def _build_cipher(client_secret: str) -> Optional[Fernet]:
    secret = (client_secret or "").strip()
    if not secret:
        return None
    if secret in _cipher_cache:
        return _cipher_cache[secret]
    try:
        key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(key_bytes)
        cipher = Fernet(key)
        _cipher_cache[secret] = cipher
        return cipher
    except Exception as e:
        logger.error(f"初始化加密器失败: {e}")
        return None


def decrypt_request_data(
    encrypted_data: str,
    client_secret: str | None = None,
) -> Optional[Dict[str, Any]]:
    """解密客户端请求数据"""
    cipher = _build_cipher(client_secret or CLIENT_SECRET)
    if not cipher:
        return None
    try:
        decrypted = cipher.decrypt(encrypted_data.encode("utf-8"))
        return json.loads(decrypted.decode("utf-8"))
    except Exception:
        return None


def encrypt_response_data(
    data: Dict[str, Any],
    client_secret: str | None = None,
) -> Optional[str]:
    """加密响应数据"""
    cipher = _build_cipher(client_secret or CLIENT_SECRET)
    if not cipher:
        return None
    try:
        json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return cipher.encrypt(json_str.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error(f"加密失败: {e}")
        return None


def collect_client_secrets(db: Session) -> list[str]:
    """收集可用于心跳加解密的 client_secret（默认产品读 CLIENT_SECRET，其余读产品表）。"""
    from app.product_utils import client_secret_for_product

    seen: set[str] = set()
    secrets: list[str] = []

    def add(value: str | None) -> None:
        secret = (value or "").strip()
        if secret and secret not in seen:
            seen.add(secret)
            secrets.append(secret)

    for product in db.query(Product).all():
        add(client_secret_for_product(product))
    return secrets


def try_decrypt_heartbeat(
    db: Session, encrypted_data: str
) -> tuple[Optional[Dict[str, Any]], str]:
    """用 client_secret 逐一尝试解密；software_name 在加密载荷内。"""
    for client_secret in collect_client_secrets(db):
        data = decrypt_request_data(encrypted_data, client_secret)
        if data:
            return data, client_secret
    return None, ""


pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

          
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """验证令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """根据用户名获取用户"""
    return db.query(User).filter(User.username == username).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """验证用户"""
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_user(db: Session, username: str, password: str, is_admin: bool = False) -> User:
    """创建用户"""
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        is_admin=is_admin
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户（从JWT令牌）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not credentials:
        raise credentials_exception
    
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise credentials_exception
    
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    user = get_user_by_username(db, username)
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """获取当前用户（可选，不强制要求登录）"""
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        return None
    
    username: str = payload.get("sub")
    if username is None:
        return None
    
    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None
    
    return user




def init_admin_user(db: Session):
    """初始化管理员用户"""
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    
                
    existing_admin = db.query(User).filter(User.username == admin_username).first()
    if not existing_admin:
        create_user(db, admin_username, admin_password, is_admin=True)
        print(f"已创建默认管理员账户: {admin_username}")
    return admin_username, admin_password

