"""集中管理认证/加密相关的环境配置常量。

放在底层、无 app 内部依赖，供 auth、crypto、product_utils 等模块共享，
避免 auth 与 product_utils 之间通过 CLIENT_SECRET 形成的循环依赖。
"""
import os

# JWT 配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-12345678")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# 默认产品的客户端心跳加解密密钥（其余产品读各自 client_secret）
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
