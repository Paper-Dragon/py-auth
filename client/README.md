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
| 在线校验授权 | `check_authorization` | `CheckAuthorization` | `checkAuthorization` |
| 要求授权通过 | `require_authorization` | `RequireAuthorization` | `requireAuthorization` |
| 仅读取本地授权信息 | `get_authorization_info` | `GetAuthorizationInfo` | `getAuthorizationInfo` |
| 清除本地缓存 | `clear_cache` | `ClearCache` | `clearCache` |
| 获取存储根路径 | `get_client_storage_root` | `DefaultClientStorageRoot` | `getClientStorageRoot` |

## 行为说明

- `check_*` / `Check*` / `check*` 会优先尝试在线心跳
- 在线请求失败时，如果本地缓存仍在有效期内，可能返回缓存授权结果
- `get_authorization_info` / `GetAuthorizationInfo` / `getAuthorizationInfo` 只读本地，不联网；其中 `cache_remaining_time` 表示本地缓存剩余有效期，不是服务端授权到期

## 示例脚本

仓库内示例：

- `client/python/example.py`
- `client/go/examples/main.go`
- `client/ts/example.ts`

示例开发时可在 `.env` 配置 `CLIENT_SECRET`；正式发行应将**可信接入标识** `client_secret` 硬编码在源码中，不同套餐使用不同值。
