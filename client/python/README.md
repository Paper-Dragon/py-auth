# py-auth-client

Python授权客户端，用于检查设备授权状态，支持缓存和AES加密传输。

## 功能特性

- ✅ 设备授权状态检查
- ✅ 本地缓存机制（7天有效期）
- ✅ AES加密传输
- ✅ 自动设备信息收集
- ✅ 离线缓存支持

## 安装

```bash
pip install py-auth-client --extra-index-url https://www.geekery.cn/pip/simple/
```

## 快速开始

```python
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
```

## 配置

**必需参数：**
- `server_url`: 授权服务器地址
- `client_secret`: 客户端密钥（必须与服务端一致）

**可选参数：**
- `device_id`: 设备ID（不提供则自动生成）
- `software_name`: 软件名称
- `device_info`: 设备信息字典（不提供则自动收集）
- `cache_dir`: 缓存目录（默认使用系统隐藏目录）
- `enable_cache`: 是否启用缓存（默认True）
- `cache_validity_days`: 缓存有效期（天，默认7天）
- `check_interval_days`: 检查间隔（天，默认2天）

## 缓存机制

- 缓存有效期：7天
- 始终向服务端发送请求并更新本地缓存
- 在线验证失败时，在有效期内使用缓存作为后备
- 缓存文件经过混淆加密，隐藏在系统目录中

