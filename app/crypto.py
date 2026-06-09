"""客户端心跳数据的 Fernet 对称加解密。

密钥由 client_secret 经 SHA-256 派生。默认产品使用环境变量 CLIENT_SECRET，
其余产品使用各自的 client_secret。
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.config import CLIENT_SECRET
from app.models import Product

logger = logging.getLogger(__name__)

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
    """解密客户端请求数据。"""
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
    """加密响应数据。"""
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
