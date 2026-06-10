import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import add_operation_log
from app.crypto import invalidate_secret_cache
from app.database import get_db
from app.deps import require_admin
from app.epay import EPAY_PAY_TYPES
from app.models import AUTH_MODES, Device, Product, User
from app.product_resolve import count_devices_by_product, count_devices_for_product
from app.product_utils import (
    DEFAULT_PRODUCT_SOFTWARE_NAME,
    client_secret_for_product,
    display_software_name,
    generate_client_secret,
    generate_product_key as make_product_key,
    is_reserved_software_name,
    is_uuid,
    validate_product_key,
)
from app.schemas import ProductCreate, ProductOptionResponse, ProductResponse, ProductUpdate

router = APIRouter(prefix="/api/admin/products", tags=["产品管理"])

SOFTWARE_NAME_PATTERN = re.compile(r"^.{2,64}$", re.UNICODE)

PLAN_DETAIL_MAX_LEN = 2000

AUTH_MODE_DEFAULT_CONFIG = {
    "open": {},
    "manual": {},
    "paid": {"plan_on_paid": "pro", "price": "0.00", "pay_type": "wxpay", "plan_detail": ""},
}


def _validate_auth_mode(auth_mode: str) -> str:
    if auth_mode not in AUTH_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的授权模式，可选: {', '.join(AUTH_MODES)}",
        )
    return auth_mode


def _normalize_config(auth_mode: str, config: dict | None) -> dict:
    base = dict(AUTH_MODE_DEFAULT_CONFIG.get(auth_mode, {}))
    if config:
        base.update(config)
    if auth_mode == "paid":
        plan = str(base.get("plan_on_paid", "pro")).strip() or "pro"
        price = str(base.get("price", "0.00")).strip() or "0.00"
        pay_type = str(base.get("pay_type", "wxpay")).strip().lower() or "wxpay"
        if pay_type not in EPAY_PAY_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"pay_type 仅支持: {', '.join(EPAY_PAY_TYPES)}",
            )
        base["plan_on_paid"] = plan
        base["price"] = price
        base["pay_type"] = pay_type
        detail = str(base.get("plan_detail", "")).strip()
        if len(detail) > PLAN_DETAIL_MAX_LEN:
            raise HTTPException(
                status_code=400,
                detail=f"套餐详情不能超过 {PLAN_DETAIL_MAX_LEN} 字",
            )
        if detail:
            base["plan_detail"] = detail
        else:
            base.pop("plan_detail", None)
    return base


def _validate_product_key(key: str) -> str:
    try:
        return validate_product_key(key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _validate_software_name(name: str) -> str:
    name = name.strip()
    if not SOFTWARE_NAME_PATTERN.match(name):
        raise HTTPException(status_code=400, detail="软件名称须为 2~64 个字符")
    if is_uuid(name):
        raise HTTPException(status_code=400, detail="软件名称不能使用 UUID 格式的内部标识")
    if is_reserved_software_name(name):
        raise HTTPException(status_code=400, detail="软件名称已被系统保留")
    return name


def _ensure_unique_software_name(
    db: Session,
    software_name: str,
    *,
    exclude_product_id: int | None = None,
) -> None:
    query = db.query(Product).filter(Product.software_name == software_name)
    if exclude_product_id is not None:
        query = query.filter(Product.id != exclude_product_id)
    if query.first():
        raise HTTPException(status_code=400, detail="软件名称已存在")


def _to_product_response(product: Product, device_count: int = 0) -> ProductResponse:
    secret = client_secret_for_product(product)
    return ProductResponse(
        id=product.id,
        key=product.key,
        software_name=display_software_name(product),
        display_name=display_software_name(product),
        auth_mode=product.auth_mode,
        config=product.config,
        is_active=product.is_active,
        is_default=bool(product.is_default),
        device_count=device_count,
        client_secret=secret,
        client_secret_configured=bool(secret),
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.get("/options", response_model=list[ProductOptionResponse])
async def list_product_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    products = (
        db.query(Product)
        .order_by(Product.is_default.desc(), Product.display_name.asc())
        .all()
    )
    return [
        ProductOptionResponse(
            key=product.key,
            software_name=display_software_name(product),
            display_name=display_software_name(product)
            if product.is_default
            else (product.display_name or display_software_name(product)),
            is_active=product.is_active,
        )
        for product in products
    ]


@router.get("", response_model=list[ProductResponse])
async def list_products(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    products = (
        db.query(Product)
        .order_by(Product.is_default.desc(), Product.created_at.desc())
        .all()
    )
    counts = count_devices_by_product(db, products)
    return [_to_product_response(p, counts.get(p.key, 0)) for p in products]


@router.post("", response_model=ProductResponse)
async def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    auth_mode = _validate_auth_mode(data.auth_mode)
    key = _validate_product_key(data.key) if data.key else make_product_key()

    if db.query(Product).filter(Product.key == key).first():
        raise HTTPException(status_code=400, detail="产品 Key 已存在")

    software_name = _validate_software_name(data.software_name)
    _ensure_unique_software_name(db, software_name)

    display_name = (data.display_name or software_name).strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="显示名称不能为空")

    product = Product(
        key=key,
        software_name=software_name,
        client_secret=generate_client_secret(),
        display_name=display_name,
        auth_mode=auth_mode,
        config=_normalize_config(auth_mode, data.config),
        is_active=data.is_active if data.is_active is not None else True,
    )
    db.add(product)
    add_operation_log(
        db,
        username=current_user.username,
        action="create_product",
        target_type="product",
        target_id=key,
        detail={
            "software_name": software_name,
            "display_name": display_name,
            "auth_mode": auth_mode,
            "is_active": product.is_active,
        },
    )
    db.commit()
    invalidate_secret_cache()
    db.refresh(product)
    return _to_product_response(product, 0)


@router.post("/generate-key")
async def generate_product_key_endpoint(
    _: User = Depends(require_admin),
):
    return {"key": make_product_key()}


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    updates = data.model_dump(exclude_unset=True)
    if product.is_default and any(
        key in updates for key in ("software_name", "key")
    ):
        raise HTTPException(status_code=400, detail="默认产品不可修改软件名称或内部标识")

    if "software_name" in updates and updates["software_name"] is not None:
        software_name = _validate_software_name(updates["software_name"])
        _ensure_unique_software_name(db, software_name, exclude_product_id=product_id)
        product.software_name = software_name

    if "display_name" in updates:
        display_name = (updates["display_name"] or "").strip()
        if not display_name:
            raise HTTPException(status_code=400, detail="显示名称不能为空")
        product.display_name = display_name

    if "auth_mode" in updates and updates["auth_mode"] is not None:
        product.auth_mode = _validate_auth_mode(updates["auth_mode"])

    if "config" in updates:
        product.config = _normalize_config(product.auth_mode, updates["config"])
    elif "auth_mode" in updates:
        product.config = _normalize_config(product.auth_mode, product.config)

    if "is_active" in updates and updates["is_active"] is not None:
        product.is_active = updates["is_active"]

    product.updated_at = datetime.now()
    add_operation_log(
        db,
        username=current_user.username,
        action="update_product",
        target_type="product",
        target_id=product.key,
        detail={"updated_fields": list(updates.keys()), "product_id": product_id},
    )
    db.commit()
    invalidate_secret_cache()
    db.refresh(product)

    return _to_product_response(product, count_devices_for_product(db, product))


@router.post("/{product_id}/regenerate-client-secret", response_model=ProductResponse)
async def regenerate_product_client_secret(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.is_default:
        raise HTTPException(
            status_code=400,
            detail="默认产品 Client Secret 来自环境变量 CLIENT_SECRET，不可在此修改",
        )

    product.client_secret = generate_client_secret()
    product.updated_at = datetime.now()
    add_operation_log(
        db,
        username=current_user.username,
        action="regenerate_product_client_secret",
        target_type="product",
        target_id=product.key,
        detail={"product_id": product_id},
    )
    db.commit()
    invalidate_secret_cache()
    db.refresh(product)

    return _to_product_response(product, count_devices_for_product(db, product))


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    if product.is_default:
        raise HTTPException(status_code=400, detail="默认产品不可删除，请在产品管理中调整其授权策略")

    key = product.key
    db.delete(product)
    add_operation_log(
        db,
        username=current_user.username,
        action="delete_product",
        target_type="product",
        target_id=key,
        detail={"product_id": product_id},
    )
    db.commit()
    invalidate_secret_cache()
    return {"message": "产品已删除"}
