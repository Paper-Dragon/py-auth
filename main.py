from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from app.database import engine, Base, SessionLocal
from app.routers import auth, admin
from app.routers import user as user_router
from app.auth import init_admin_user
from app.middleware import setup_cors
import logging
import os

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

# 静态文件服务
web_dist_path = os.path.join(os.path.dirname(__file__), "web", "dist")
if os.path.exists(web_dist_path):
    # 挂载静态资源（JS、CSS、图片等）
    assets_path = os.path.join(web_dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
    
    # 根路径返回前端页面
    @app.get("/")
    async def root():
        index_path = os.path.join(web_dist_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "前端文件未找到"}
    
    # SPA 路由支持：所有非 API 路径都返回 index.html
    # 注意：这个路由必须放在最后，因为 FastAPI 按顺序匹配路由
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # 排除 API 和文档路径（这些路由已经在上面注册了）
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path == "openapi.json":
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        
        # 检查是否是静态资源文件
        file_path = os.path.join(web_dist_path, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # 其他路径返回 index.html（支持前端路由）
        index_path = os.path.join(web_dist_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")
else:
    @app.get("/")
    async def root():
        """根路径"""
        return {"message": "启动成功，前端文件未构建"}

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0", 
        port=8000,
        reload=True
    )

