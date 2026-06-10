"""轻量 schema 迁移（无 Alembic 时补齐新增列）。"""
import logging

from sqlalchemy import inspect, text

from app.database import SessionLocal, engine
from app.product_utils import generate_client_secret, is_uuid

logger = logging.getLogger(__name__)


def _column_names(table: str) -> set[str]:
    insp = inspect(engine)
    insp.clear_cache()
    if table not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(table)}


def migrate_schema() -> None:
    if "products" not in inspect(engine).get_table_names():
        return

    cols = _column_names("products")
    if "client_secret" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE products ADD COLUMN client_secret VARCHAR(128)")
            )
        logger.info("已迁移 products.client_secret 列")

    cols = _column_names("products")
    if "software_name" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE products ADD COLUMN software_name VARCHAR(64)")
            )
        logger.info("已迁移 products.software_name 列")

    cols = _column_names("products")
    if "is_default" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE products ADD COLUMN is_default BOOLEAN DEFAULT 0")
            )
        logger.info("已迁移 products.is_default 列")

    _backfill_product_software_names()
    _backfill_product_client_secrets()
    _migrate_legacy_auth_modes()
    ensure_default_product()
    _migrate_devices_product_key()
    _migrate_devices_is_banned()
    _migrate_devices_manual_plan()


def _migrate_legacy_auth_modes() -> None:
    """已废弃的 trial/hybrid 授权模式统一迁移为 manual（手动审核）。"""
    from app.models import AUTH_MODE_MANUAL, Product

    db = SessionLocal()
    try:
        products = (
            db.query(Product)
            .filter(Product.auth_mode.in_(("trial", "hybrid")))
            .all()
        )
        if not products:
            return
        for product in products:
            product.auth_mode = AUTH_MODE_MANUAL
            product.config = {}
        db.commit()
        logger.info("已将 %s 个 trial/hybrid 产品迁移为 manual 模式", len(products))
    except Exception as exc:
        db.rollback()
        logger.error("迁移废弃授权模式失败: %s", exc)
    finally:
        db.close()


def _backfill_product_software_names() -> None:
    from app.models import Product

    db = SessionLocal()
    try:
        products = (
            db.query(Product)
            .filter((Product.software_name.is_(None)) | (Product.software_name == ""))
            .all()
        )
        if not products:
            return

        used: set[str] = set()
        for row in db.query(Product.software_name).all():
            name = row[0] if isinstance(row, tuple) else row
            if name and str(name).strip():
                used.add(str(name).strip())

        for product in products:
            candidates: list[str] = []
            display = (product.display_name or "").strip()
            key = (product.key or "").strip()
            if display:
                candidates.append(display)
            if key and not is_uuid(key) and not key.startswith("prod_"):
                candidates.append(key)

            chosen = ""
            for candidate in candidates:
                if candidate and candidate not in used:
                    chosen = candidate
                    break
            if not chosen and display:
                base = display
                suffix = 1
                chosen = base
                while chosen in used:
                    suffix += 1
                    chosen = f"{base}_{suffix}"[:64]

            if chosen:
                product.software_name = chosen
                used.add(chosen)

        db.commit()
        logger.info("已为 %s 个产品回填 software_name", len(products))
    except Exception as exc:
        db.rollback()
        logger.error("回填 software_name 失败: %s", exc)
    finally:
        db.close()


def _migrate_devices_product_key() -> None:
    if "devices" not in inspect(engine).get_table_names():
        return

    cols = _column_names("devices")
    if "product_key" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE devices ADD COLUMN product_key VARCHAR(64)")
            )
        logger.info("已迁移 devices.product_key 列")

    _backfill_device_product_keys()


def _migrate_devices_is_banned() -> None:
    if "devices" not in inspect(engine).get_table_names():
        return

    cols = _column_names("devices")
    if "is_banned" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE devices ADD COLUMN is_banned BOOLEAN DEFAULT 0")
            )
        logger.info("已迁移 devices.is_banned 列")


def _migrate_devices_manual_plan() -> None:
    if "devices" not in inspect(engine).get_table_names():
        return

    cols = _column_names("devices")
    if "manual_plan" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE devices ADD COLUMN manual_plan VARCHAR(64)")
            )
        logger.info("已迁移 devices.manual_plan 列")


def _backfill_device_product_keys() -> None:
    from app.models import Device
    from app.product_resolve import get_default_product, resolve_product

    db = SessionLocal()
    try:
        default_product = get_default_product(db)
        devices = (
            db.query(Device)
            .filter((Device.product_key.is_(None)) | (Device.product_key == ""))
            .all()
        )
        if not devices:
            return
        for device in devices:
            product = resolve_product(db, device.software_name) or default_product
            if product:
                device.product_key = product.key
        db.commit()
        logger.info("已为 %s 台设备回填 product_key", len(devices))
    except Exception as exc:
        db.rollback()
        logger.error("回填 devices.product_key 失败: %s", exc)
    finally:
        db.close()


def _repair_default_product_row(product) -> bool:
    from app.product_utils import (
        DEFAULT_PRODUCT_DISPLAY_NAME,
        DEFAULT_PRODUCT_SOFTWARE_NAME,
        LEGACY_DEFAULT_PRODUCT_DISPLAY_NAME,
    )

    changed = False
    if (product.software_name or "").strip() != DEFAULT_PRODUCT_SOFTWARE_NAME:
        product.software_name = DEFAULT_PRODUCT_SOFTWARE_NAME
        changed = True
    display_name = (product.display_name or "").strip()
    if not display_name or display_name == LEGACY_DEFAULT_PRODUCT_DISPLAY_NAME:
        product.display_name = DEFAULT_PRODUCT_DISPLAY_NAME
        changed = True
    if (product.client_secret or "").strip():
        product.client_secret = None
        changed = True
    return changed


def ensure_default_product() -> None:
    from app.coerce import coerce_boolish
    from app.models import AUTH_MODE_MANUAL, AUTH_MODE_OPEN, Config, Product
    from app.product_utils import (
        DEFAULT_PRODUCT_DISPLAY_NAME,
        DEFAULT_PRODUCT_SOFTWARE_NAME,
        generate_product_key,
    )

    db = SessionLocal()
    try:
        defaults = (
            db.query(Product)
            .filter(Product.is_default.is_(True))
            .order_by(Product.id.asc())
            .all()
        )
        changed = False
        if len(defaults) > 1:
            for duplicate in defaults[1:]:
                duplicate.is_default = False
                changed = True
            defaults = defaults[:1]

        default_product = defaults[0] if defaults else None
        if default_product is None:
            orphan = (
                db.query(Product)
                .filter(Product.software_name == DEFAULT_PRODUCT_SOFTWARE_NAME)
                .order_by(Product.id.asc())
                .first()
            )
            if orphan:
                orphan.is_default = True
                default_product = orphan
                changed = True

        if default_product is not None:
            if _repair_default_product_row(default_product):
                changed = True
            if changed:
                db.commit()
                logger.info("已修复默认产品配置")
            return

        config = db.query(Config).filter(Config.key == "default_authorization").first()
        default_open = coerce_boolish(config.value if config else True, if_none=True)
        auth_mode = AUTH_MODE_OPEN if default_open else AUTH_MODE_MANUAL

        product = Product(
            key=generate_product_key(),
            software_name=DEFAULT_PRODUCT_SOFTWARE_NAME,
            display_name=DEFAULT_PRODUCT_DISPLAY_NAME,
            auth_mode=auth_mode,
            config={},
            is_active=True,
            is_default=True,
            client_secret=None,
        )
        db.add(product)
        db.commit()
        logger.info("已创建默认产品，兜底未登记 software_name 的授权策略")
    except Exception as exc:
        db.rollback()
        logger.error("创建默认产品失败: %s", exc)
    finally:
        db.close()


def _backfill_product_client_secrets() -> None:
    from app.models import Product

    db = SessionLocal()
    try:
        products = (
            db.query(Product)
            .filter((Product.client_secret.is_(None)) | (Product.client_secret == ""))
            .all()
        )
        if not products:
            return
        for product in products:
            if product.is_default:
                continue
            product.client_secret = generate_client_secret()
        db.commit()
        logger.info("已为 %s 个产品生成 client_secret", len(products))
    except Exception as exc:
        db.rollback()
        logger.error("回填产品 client_secret 失败: %s", exc)
    finally:
        db.close()
