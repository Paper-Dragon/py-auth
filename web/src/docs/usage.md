## 设备字段说明

本文说明管理后台设备列表和详情页中的主要字段含义。

### 设备 ID `device_id`

`device_id` 由客户端生成，管理后台仅负责展示，用于区分不同设备。公开支付页下单时也使用该 ID。

### 软件名称 `software_name`

客户端上报的展示名称。授权策略按 `client_secret` 解析到的产品 UUID（`product_key`）执行，与 `software_name` 无强绑定关系。

### 设备详情 `device_info`

管理后台以 JSON 形式展示 `device_info`。官方客户端会自动附带 `device_info.sdk`。

| 字段 | 说明 |
|------|------|
| `language` | SDK 语言，取值通常为 `python`、`go`、`typescript` |
| `sdk_name` | SDK 名称 |
| `sdk_version` | SDK 版本 |
| `runtime` | 运行时版本 |
| `heartbeat_times` | 当前设备累计成功心跳次数 |

设备快照 `device_info_snapshot` 会在授权成功后落盘，不包含当次 `sdk.heartbeat_times`。

### 常见子对象

| 字段 | 说明 |
|------|------|
| `system` | 主机名、操作系统、内核、机器信息、用户名、运行时长等 |
| `network` | MAC、IP、网络接口、公网 IP 等 |
| `memory` | 内存总量、空闲量、可用量 |
| `cpu` | CPU 型号、核心数、频率等 |
| `disk` | 磁盘摘要与卷信息 |

旧版本数据中的字段名可能不同，应以实际返回的 JSON 结构为准。

## 时间字段

| 字段 | 更新时机 | 含义 |
|------|----------|------|
| `created_at` | 设备首次请求时写入，之后不再改变 | 注册时间 |
| `updated_at` | 管理员修改授权、备注，或设备上报的 `software_name`、`device_info` 发生变化时更新 | 最近一次设备记录变更时间 |
| `last_check` | 每次成功心跳或授权校验时更新 | 最近一次成功校验时间 |

## 产品管理

| 列 / 字段 | 说明 |
|-----------|------|
| 软件名称 | 客户端 `software_name` 与展示用名称；默认产品显示为「未登记产品（默认）」 |
| UUID | 产品内部标识 `product.key`，由 `client_secret` 解析得到 |
| Client Secret | 心跳加解密密钥；默认产品读取环境变量 `CLIENT_SECRET` |
| 授权模式 | 开放 / 手动审核 / 试用 / 付费 / 免费+付费 |
| 授权配置 | 当前模式下的参数摘要，如试用天数、价格与支付方式 |
| 设备数 | 已绑定该产品 UUID 的设备数量 |

## 易支付与支付页

- **支付页**：对外公开地址 `{PUBLIC_BASE_URL}/pay?device_id=xxx`，在「易支付」页查看解析结果
- 须先配置 `PUBLIC_BASE_URL` 或填写完整「同步跳转」URL，后台才会显示生产域名链接（不会用 `localhost` 充当对外地址）
- 设备须先完成客户端心跳，支付页才能解析产品与价格

更多说明见仓库根目录 [docs/dev/payment.md](../../../../docs/dev/payment.md)。

## 常见问题

**为什么 `last_check` 经常变化？**  
因为每次成功心跳或授权校验都会刷新该字段。

**`updated_at` 和 `last_check` 有什么区别？**  
`updated_at` 表示设备记录发生变更的时间，`last_check` 表示最近一次成功校验的时间。

**`created_at` 可以修改吗？**  
不可以。该字段在设备首次写入时确定。

**支付页提示「设备未绑定产品」？**  
请先用对应 `client_secret` 完成一次客户端心跳，再打开支付页。
