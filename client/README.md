# 客户端 SDK

本目录提供 Python、Go、TypeScript 三种客户端 SDK。

这些 SDK 共享同一套协议约定，适用于：

- 启动时执行授权校验
- 运行中定期执行在线心跳
- 离线时读取本地授权缓存

## 文档索引

| 文档 | 说明 |
|------|------|
| [client/python/README.md](python/README.md) | Python 客户端 SDK 使用说明 |
| [client/go/README.md](go/README.md) | Go 客户端 SDK 使用说明 |
| [client/ts/README.md](ts/README.md) | TypeScript 客户端 SDK 使用说明 |
| [docs/dev/client-storage.md](../docs/dev/client-storage.md) | 存储、状态文件、加解密和 `device_id` 约定 |
| [docs/dev/payment.md](../docs/dev/payment.md) | 易支付、公网地址与公开支付页 |
| [web/src/docs/usage.md](../web/src/docs/usage.md) | 管理后台中设备字段的展示含义 |

## 公共方法对照

| 语义 | Python | Go | TypeScript |
|------|--------|----|------------|
| 设备 ID / 服务地址 | `device_id` / `server_url` | `DeviceID()` / `ServerURL()` | `deviceId` / `serverUrl` |
| 在线校验授权 | `check_authorization` | `CheckAuthorization` | `checkAuthorization` |
| 渐进式在线校验 | `check_authorization_progressive` | `CheckAuthorizationProgressive` | `checkAuthorizationProgressive` |
| 要求授权通过 | `require_authorization` | `RequireAuthorization` | `requireAuthorization` |
| 要求授权（可不抛异常） | `require_authorization(raise_exception=False)` | `RequireAuthorizationEx(forceOnline, false)` | `requireAuthorization({ raiseException: false })` |
| 本地快照可软启动 | `can_soft_launch` | `CanSoftLaunch` | `canSoftLaunch` |
| 后台刷新授权 | `start_background_refresh` | `StartBackgroundRefresh` | `startBackgroundRefresh` |
| 异步提交在线校验 | `submit_check_authorization` | `SubmitCheckAuthorization` | `submitCheckAuthorization` |
| 异步提交渐进校验 | `submit_check_authorization_progressive` | `SubmitCheckAuthorizationProgressive` | `submitCheckAuthorizationProgressive` |
| 异步提交要求授权 | `submit_require_authorization` | `SubmitRequireAuthorization` | `submitRequireAuthorization` |
| 仅读取本地授权信息 | `get_authorization_info` | `GetAuthorizationInfo` | `getAuthorizationInfo` |
| 读取缓存详情 | `get_cache_info` | `GetCacheInfo` | `getCacheInfo` |
| 查询套餐信息（加密 API） | `get_plan_info` | `GetPlanInfo` | `getPlanInfo` |
| 查询设备付费上下文 | `get_payment_context` | `GetPaymentContext` | `getPaymentContext` |
| HTTP 超时配置 | `heartbeat_timeout_sec` / `plan_info_timeout_sec` / `payment_context_timeout_sec` | `HeartbeatTimeout` / `PlanInfoTimeout` / `PaymentContextTimeout` | `heartbeatTimeoutMs` / `planInfoTimeoutMs` / `paymentContextTimeoutMs` |
| 判断超时错误 | `AuthorizationError.is_timeout` | `AuthorizationError.IsTimeout()` | `AuthorizationError.isTimeout()` |
| 清除本地缓存 | `clear_cache` | `ClearCache` | `clearCache` |
| 获取存储根路径 | `get_client_storage_root` | `DefaultClientStorageRoot` | `getClientStorageRoot` |

### 套餐信息 API 返回字段

`get_plan_info` / `getPlanInfo` / `GetPlanInfo` 与 `get_payment_context` 中的套餐字段一致：

| 字段 | 说明 |
|------|------|
| `plan` | 付费档位代号，如 `pro` |
| `plan_detail` | 套餐详情文案 |
| `price` | 价格（付费模式） |
| `pay_type` | 支付方式 |
| `can_pay` | 是否可发起支付 |
| `auth_mode` | 产品授权模式 |

心跳返回的 `authorized` 表示**能否上线**；管理员封禁后即为 `false`，与是否已配置套餐无关。

## HTTP 超时默认值

三端对不同类型请求使用独立超时，避免辅助接口与心跳共用短时限：

| 请求 | 默认超时 |
|------|----------|
| 心跳 `/api/auth/heartbeat` | 3s |
| 套餐 `/api/auth/plan-info` | 10s（连接 5s + 读取 10s，Python） |
| 付费上下文 `/api/payment/device-context` | 10s |

传 `0` 或未配置时使用上表默认值。弱网场景可单独加大 `plan-info` / `device-context` 超时。

## 行为说明

- `check_*` / `Check*` / `check*` 会优先尝试在线心跳
- 在线请求失败时，如果本地缓存仍在有效期内，可能返回缓存授权结果
- `get_authorization_info` / `GetAuthorizationInfo` / `getAuthorizationInfo` 只读本地，不联网；其中 `cache_remaining_time` 表示本地缓存剩余有效期，不是服务端授权到期

## 示例脚本

仓库内示例：

- `client/python/example.py`
- `client/python/example_background.py`
- `client/go/examples/main.go`
- `client/go/examples/background/main.go`
- `client/ts/example.ts`
- `client/ts/example_background.ts`

示例开发时可在 `.env` 配置 `CLIENT_SECRET`；正式发行应将**可信接入标识** `client_secret` 硬编码在源码中，不同套餐使用不同值。
