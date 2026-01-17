from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic_settings import BaseSettings, SettingsConfigDict
import urllib.parse
import os

class Settings(BaseSettings):
    # 数据库类型：sqlite 或 mysql
    database_type: str = "sqlite"
    # SQLite 配置
    sqlite_path: str = "auth.db"
    # MySQL 配置（当 database_type=mysql 时使用）
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "password"
    mysql_database: str = "auth_db"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # 环境变量不区分大小写
        extra="ignore"  # 忽略额外的环境变量
    )

settings = Settings()

# 根据配置选择数据库类型
if settings.database_type.lower() == "mysql":
    # 使用 MySQL
    encoded_password = urllib.parse.quote_plus(settings.mysql_password)
    DATABASE_URL = f"mysql+pymysql://{settings.mysql_user}:{encoded_password}@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}?charset=utf8mb4"
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_size=10,
        max_overflow=20,
        echo=False
    )
else:
    # 默认使用 SQLite
    if os.path.isabs(settings.sqlite_path):
        # 如果是绝对路径，直接使用
        sqlite_path = settings.sqlite_path
    else:
        # 如果是相对路径，相对于项目根目录
        sqlite_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), settings.sqlite_path)
    
    # 确保目录存在
    sqlite_dir = os.path.dirname(sqlite_path)
    if sqlite_dir and not os.path.exists(sqlite_dir):
        os.makedirs(sqlite_dir, exist_ok=True)
    
    DATABASE_URL = f"sqlite:///{sqlite_path}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,  # SQLite 需要这个参数
            "timeout": 20.0  # 锁超时时间（秒），避免无限等待
        },
        pool_pre_ping=True,  # 连接前检查连接是否有效
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

