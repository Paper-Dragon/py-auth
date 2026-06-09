"""后台用户管理业务逻辑。

集中用户的创建/校验，供 auth.init_admin_user 与 admin 路由复用，
避免密码哈希与建模逻辑分散重复。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth import get_password_hash
from app.models import User


def username_exists(db: Session, username: str) -> bool:
    return db.query(User).filter(User.username == username).first() is not None


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    is_admin: bool = False,
    is_active: bool = True,
    commit: bool = True,
) -> User:
    """创建用户。commit=False 时由调用方控制事务（便于与审计日志同批提交）。"""
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        is_admin=is_admin,
        is_active=is_active,
    )
    db.add(user)
    if commit:
        db.commit()
        db.refresh(user)
    return user
