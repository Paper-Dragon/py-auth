from fastapi import FastAPI
from dotenv import load_dotenv
from app.database import engine, Base, SessionLocal
from app.routers import auth, admin
from app.routers import user as user_router
from app.auth import init_admin_user
from app.middleware import setup_cors
import logging

# 加载 .env 文件
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建数据库表
try:
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建成功")
    
    # 初始化管理员用户
    db = SessionLocal()
    try:
        admin_username, admin_password = init_admin_user(db)
        logger.info(f"默认管理员账户: {admin_username} / {admin_password}")
    finally:
        db.close()
except Exception as e:
    logger.error(f"数据库表创建失败: {str(e)}")
    logger.warning("请确保MySQL数据库已启动并配置正确")

app = FastAPI(
    title="Python授权服务",
    description="软件授权管理系统",
    version="1.0.0"
)

# CORS配置
setup_cors(app)

# 注册路由
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(user_router.router)

@app.get("/")
async def root():
    """根路径"""
    return "启动成功"

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0", 
        port=8000,
        reload=True
    )

