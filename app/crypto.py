"""客户端心跳数据的 Fernet 对称加解密。

密钥由 client_secret 经 SHA-256 派生。默认产品使用环境变量 CLIENT_SECRET，
其余产品使用各自的 client_secret。
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.config import CLIENT_SECRET
from app.models import Product

logger = logging.getLogger(__name__)

_cipher_cache: dict[str, Fernet] = {}

_SECRET_CACHE_TTL = 30  # seconds
_secret_product_cache: list[tuple[str, Product]] | None = None
_secret_cache_ts: float = 0.0
_secret_cache_lock = threading.Lock()


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


def invalidate_secret_cache() -> None:
    """产品变更时调用，立即失效 client_secret 缓存。"""
    global _secret_product_cache, _secret_cache_ts
    with _secret_cache_lock:
        _secret_product_cache = None
        _secret_cache_ts = 0.0


def _load_secret_product_pairs(db: Session) -> list[tuple[str, Product]]:
    """从数据库加载 (client_secret, product) 列表，带 TTL 缓存。"""
    global _secret_product_cache, _secret_cache_ts
    now = time.time()
    if _secret_product_cache is not None and (now - _secret_cache_ts) < _SECRET_CACHE_TTL:
        return _secret_product_cache

    from app.product_utils import client_secret_for_product

    seen: set[str] = set()
    pairs: list[tuple[str, Product]] = []
    for product in db.query(Product).all():
        secret = (client_secret_for_product(product) or "").strip()
        if not secret or secret in seen:
            continue
        seen.add(secret)
        pairs.append((secret, product))

    with _secret_cache_lock:
        _secret_product_cache = pairs
        _secret_cache_ts = now
    return pairs


def try_decrypt_heartbeat(
    db: Session, encrypted_data: str
) -> tuple[Optional[Dict[str, Any]], str, Optional[Product]]:
    """用各产品的 client_secret 逐一尝试解密，返回 (data, client_secret, product)。"""
    for secret, product in _load_secret_product_pairs(db):
        data = decrypt_request_data(encrypted_data, secret)
        if data:
            return data, secret, product
    return None, "", None
