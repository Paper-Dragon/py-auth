"""
授权客户端使用示例

缓存策略：
- 始终向服务端发送请求并更新本地缓存
- 缓存有效期7天
- 网络失败时，在有效期内使用缓存作为后备
"""
from py_auth_client import AuthClient, AuthorizationError

# 初始化客户端
client = AuthClient(
    server_url="http://localhost:8000",
    software_name="我的软件",
    client_secret="your-client-secret-key-change-in-production"
)

# 检查授权
try:
    client.require_authorization()
    print("✅ 设备已授权")
except AuthorizationError as e:
    print(f"❌ 授权失败: {e}")
    exit(1)

# 你的软件代码...
