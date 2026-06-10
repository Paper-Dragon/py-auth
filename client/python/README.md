# Python 客户端 SDK

## 依赖关系

| 文档 | 说明 |
|------|------|
| [client/README.md](../README.md) | SDK 总览与三端方法对照 |
| [docs/dev/client-storage.md](../../docs/dev/client-storage.md) | 存储、`device_id`、状态文件与加解密约定 |
| [docs/dev/payment.md](../../docs/dev/payment.md) | 付费授权与公开支付页 |

## 安装

```bash
pip install py-auth-client --extra-index-url https://www.geekery.cn/pip/simple/
```

## `AuthClient` 参数

| 参数 | 是否必需 | 说明 |
|------|----------|------|
| `server_url` | 必填 | 服务地址 |
| `software_name` | 必填 | 写在加密载荷里，用于授权校验（默认/手动审核/付费等）；填后台登记的软件名称，不是内部 UUID |
| `client_secret` | 条件必填 | **可信接入标识**，硬编码在发行包中（不同套餐/版本使用不同值）；服务端信任该标识做心跳加解密并确定 **套餐 plan**。开发调试可用环境变量 `CLIENT_SECRET` |
| `device_id` | 可选 | 省略时自动生成或复用 |
| `device_info` | 可选 | 省略时自动采集 |
| `cache_validity_days` | 可选 | 本地缓存有效期，默认 `7` |
| `check_interval_days` | 可选 | 检查间隔，默认 `2` |
| `debug` | 可选 | 是否输出调试日志 |
| `software_version` | 可选 | 软件版本 |
| `heartbeat_timeout_sec` | 可选 | 心跳超时（秒或 `(connect, read)` 元组）；默认 `(3.0, 3.0)` |
| `plan_info_timeout_sec` | 可选 | 套餐查询超时；默认 `(5.0, 10.0)` |
| `payment_context_timeout_sec` | 可选 | 付费上下文查询超时；默认 `(5.0, 10.0)` |

### 关于 `client_secret`（可信接入标识）

发行时把 `client_secret` 写进源码，随安装包分发：

- 它是服务端**信任的标识**，用于识别客户端发行渠道/套餐，并返回对应 `plan`
- **免费版 / Pro 版** 可各自硬编码不同标识
- 与 `software_name` 分工：`software_name` 走授权规则（手动审核、付费等），`client_secret` 走套餐归属
- 轮换 `client_secret` 会使旧发行包标识失效，需发新包（后台产品列表可复制当前密钥）

## 示例

### 启动时要求授权通过

```python
from py_auth_client import AuthClient, AuthorizationError

client = AuthClient(
    server_url="http://localhost:8000",
    software_name="我的软件",
    client_secret="sk_...",  # 可信接入标识，硬编码，与后台一致
)

try:
    client.require_authorization()
except AuthorizationError as e:
    raise SystemExit(f"授权失败: {e}")
```

### 检查授权并按结果处理

```python
result = client.check_authorization()

if result.get("success") and result.get("authorized"):
    print("已授权")
else:
    print("未授权或校验失败：", result.get("message", ""))
```

### 仅读取本地授权信息

```python
info = client.get_authorization_info()
print(
    info.get("authorized"),
    info.get("message"),
    info.get("device_id"),
    info.get("cache_remaining_time"),
)
```

常见字段包括：

- `authorized`
- `message`
- `device_id`
- `server_url`
- `cache_remaining_time`：本地缓存剩余有效时间（默认 7 天，由 `cache_validity_days` 控制），**不是**服务端授权到期
- `cache_valid`

### 查询套餐信息

```python
plan = client.get_plan_info()
if plan.get("success"):
    print(plan.get("plan"), plan.get("price"))
    if plan.get("plan_detail"):
        print(plan.get("plan_detail"))

ctx = client.get_payment_context()
if ctx.get("success"):
    print(ctx.get("plan"), ctx.get("can_pay"))
```

`get_plan_info()` 返回产品套餐配置（档位、价格、详情等），不表示本机是否已付款。心跳返回的 `authorized` 表示能否上线；`plan` 表示当前生效档位。

### 读取缓存详情

```python
cache = client.get_cache_info()
```

### 后台刷新授权

```python
soft, fut = client.start_background_refresh(on_done=lambda r: print(r))
result = fut.result(timeout=120)
```

### 清除本地缓存

```python
client.clear_cache()
```

### 不抛异常，直接返回布尔值

```python
ok = client.require_authorization(raise_exception=False)
print(ok)
```

开发与发布说明见 [docs/dev/client-python-release.md](../../docs/dev/client-python-release.md)。
