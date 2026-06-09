# 客户端本地存储与状态文件

本文面向开发与维护，说明客户端 SDK 的本地存储路径、状态文件格式、加解密约定和缓存行为。

## 相关文档

| 文档 | 说明 |
|------|------|
| [client/README.md](../../client/README.md) | 客户端 SDK 总览 |
| [client/python/README.md](../../client/python/README.md) | Python 客户端 SDK 使用说明 |
| [client/go/README.md](../../client/go/README.md) | Go 客户端 SDK 使用说明 |
| [client/ts/README.md](../../client/ts/README.md) | TypeScript 客户端 SDK 使用说明 |
| [docs/dev/payment.md](payment.md) | 易支付与公开支付页 |
| [web/src/docs/usage.md](../../web/src/docs/usage.md) | 后台设备字段说明 |

## 1. 默认存储根

| 系统 | 路径 |
|------|------|
| Windows | `%ProgramData%\\.RuntimeRepository` |
| Linux / macOS | 系统临时目录下 `.runtime-repository` |

各端由以下接口决定存储根：

- Python：`get_client_storage_root`
- Go：`DefaultClientStorageRoot`
- TypeScript：`getClientStorageRoot`

首次写入前会自动创建目录。

## 2. 状态文件命名

状态文件名格式：

```text
state_{serverHash12}_default.dat
```

规则：

- 先对 `server_url` 执行 `strip` 并移除尾部 `/`
- 对规范化后的 URL 做 UTF-8 编码
- 计算 `SHA256`
- 取十六进制结果前 12 位作为 `serverHash12`

## 3. 状态文件内容

状态文件根对象为 JSON，键为各产品的 `software_name`。

根级保留键：

- `apps`
- `heartbeat_times`
- `device_id`
- `last_success_at`

常见条目字段：

| 字段 | 说明 |
|------|------|
| `device_id` | 当前产品对应的设备 ID |
| `last_success_at` | 最近一次成功落盘的 Unix 时间戳，单位为秒 |
| `heartbeat_times` | 成功心跳累计次数 |
| `device_info_snapshot` | 最近一次成功时的 `device_info` 快照 |

## 4. 状态文件加密

状态包文件使用 `AES-256-GCM`。

密钥规则：

- 对规范化后的 `server_url` 执行 UTF-8 编码
- 计算 `SHA256`
- 取 32 字节结果作为 AES-256 密钥

磁盘字节格式：

```text
12 字节 nonce + 密文 + 16 字节 tag
```

## 5. `client_secret`（可信接入标识）

须与服务端对应产品登记的标识一致。

用途：

- 在线心跳加解密
- 服务端**信任**该标识，据此确定套餐 `plan`（绑定产品，非 `software_name`）
- 不参与状态文件 AES 密钥生成，不写入状态文件

发行约定：

- **正式软件**：硬编码在发行包中，不同版本/套餐使用不同标识
- **开发调试**：可用环境变量 `CLIENT_SECRET`

## 6. `device_id`

三端尽量对齐 Python 的 `build_device_id` 规则，但不同平台的硬件与系统信息来源可能存在轻微差异。  
如果要求完全一致，应显式传入同一个 `device_id`。

## 7. 本地读写行为

- `check_*` / `Check*` / `check*`：读取本地状态，发起在线心跳，成功后更新缓存与快照
- `require_*` / `Require*` / `require*`：基于授权检查结果决定是否抛错或返回失败
- `get_*_authorization_info` / `GetAuthorizationInfo` / `getAuthorizationInfo`：只读本地，不联网

`cache_validity_days` 只影响是否继续信任本地缓存中的授权信息。

### `get_authorization_info` 常见字段

| 字段 | 含义 |
|------|------|
| `authorized` | 本地缓存中记录的授权结果 |
| `cache_valid` | 缓存是否在 `cache_validity_days` 有效期内 |
| `cache_remaining_time` | **本地缓存**剩余有效时间（如 `6天23小时59分钟`），离线时仍可信任缓存的倒计时 |
| `cached_at` / `cached_at_readable` | 最近一次成功在线校验并写入缓存的时间 |

**注意**：`cache_remaining_time` 不是服务端授权到期时间。付费授权等业务期限由服务端心跳返回的 `message` / `plan` 决定，客户端不会将其换算为倒计时写入该字段。

## 8. 多客户端共享状态文件

多个客户端可共享同一个状态文件，但必须满足以下条件：

- 使用相同的规范化 `server_url`
- 使用相同的存储根
- 使用相同的状态文件命名规则

不同产品通过根对象中的不同 `software_name` 键分隔。

## 9. 调试工具

可使用以下工具解密状态文件：

```bash
python tools/decrypt_state_bundle.py
```

必要时可传入目标文件路径。执行前需保证 `server_url` 与客户端实际使用值一致。
