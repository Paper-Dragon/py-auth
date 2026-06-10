# 支付与公网地址

本文说明易支付接入、公开支付页与生产环境地址配置。

## 功能概览

- **产品管理**：为每个软件配置授权模式（默认、手动审核、付费）及价格、支付方式
- **公开支付页**：`/pay`，用户凭 `device_id` 为设备购买授权
- **易支付**：对接易支付网关，支持支付宝、微信、QQ 钱包
- **订单管理**：后台查看、同步订单状态

## 公网地址 `PUBLIC_BASE_URL`

生产环境**必须**配置公网访问根地址，用于：

- 自动生成易支付异步通知 URL（`/api/payment/epay/notify`）
- 自动生成支付结果页跳转 URL（`/pay/result`）
- 后台「易支付」页展示对外支付页链接（`/pay`）

在 `.env` 中设置：

```env
PUBLIC_BASE_URL=https://auth.example.com
```

也可在后台「易支付 → 同步跳转」填写完整 URL（如 `https://auth.example.com/pay/result`），系统会从中解析站点根地址。

**注意**：未配置公网地址时，后台不会用 `localhost` 充当对外链接，支付页地址将显示为「请配置 PUBLIC_BASE_URL 或同步跳转地址」。

### 地址解析优先级

1. 环境变量 `PUBLIC_BASE_URL`
2. 「同步跳转」字段中的完整 URL 的站点根（`scheme + host`）
3. 当前 HTTP 请求 Host（仅用于服务端实际生成回调，**不**用于后台展示的支付页链接）

## 易支付配置

可在 `.env` 预填，或在后台 **易支付** 页面配置：

| 字段 | 说明 |
|------|------|
| `EPAY_API_URL` / 接口地址 | 易支付网关根地址 |
| `EPAY_PID` / 商户 ID | 商户 PID |
| `EPAY_KEY` / 商户密钥 | 用于签名与验签 |
| `EPAY_NOTIFY_URL` | 异步通知，留空则自动生成 |
| `EPAY_RETURN_URL` | 同步跳转，留空则自动生成 `/pay/result` |

保存后可在同一页面查看 **实际回调**、**实际跳转**、**支付页** 三类解析结果。

### 网关对接说明

服务端易支付实现基于 [ezfpy 官方 Python SDK](https://www.ezfpy.cn/download/python.zip)（`app/ezfpy_sdk.py`）：

| 能力 | 接口 |
|------|------|
| 页面跳转支付 | `submit.php` |
| API 支付（二维码/跳转） | `mapi.php` |
| 订单查询（同步） | `api/findorder` |

部分网关不提供 `api.php?act=query` / `act=order`。**连接测试**仅验证网关可达，不会创建测试订单；验证支付请使用「测试支付」并由管理员扫码完成。

接口地址填写网关根地址即可，例如 `https://www.ezfpy.cn`，不要包含 `mapi.php` 等路径。

## 套餐信息字段

客户端 `POST /api/auth/plan-info` 与公开接口 `GET /api/payment/device-context` 返回的套餐相关字段：

| 字段 | 说明 |
|------|------|
| `display_name` | 产品展示名 |
| `software_name` | 软件名称 |
| `auth_mode` | `open` / `manual` / `paid` |
| `plan` | 付费档位代号（产品配置中的「付费档位」） |
| `plan_detail` | 套餐详情文案（产品配置中填写） |
| `price` | 价格（仅付费模式） |
| `pay_type` | 支付方式 |
| `can_pay` | 当前是否可发起支付 |

`plan-info` 描述**产品套餐配置**，不表示某台设备是否已付款或是否被封禁。设备付款状态见管理后台「套餐信息」列；授权权益与封禁分别见「授权状态」「封禁状态」两列。

## 支付流程

```text
客户端心跳（绑定 device_id + product_key）
        ↓
用户打开支付页 /pay?device_id=xxx
        ↓
服务端按设备绑定产品解析价格与支付方式
        ↓
创建订单 → 跳转易支付
        ↓
支付成功 → 异步通知入账并授权设备
        ↓
浏览器跳转 /pay/result（带易支付签名参数）
```

### 支付页参数

| 参数 | 说明 |
|------|------|
| `device_id` | 必填，与客户端生成并心跳上报的设备 ID 一致 |
| `auto_pay` | 可选，设为 `1` 时进入页面后自动下单 |

示例：

```text
https://auth.example.com/pay?device_id=your-device-id
```

### 订单查询（公开接口）

`GET /api/payment/orders/{out_trade_no}` 为公开接口，但须携带与订单一致的 `device_id` 查询参数，否则返回 404，避免订单信息被枚举。

支付结果页在跳转回来时会通过 `sessionStorage` 或 URL 中的 `device_id` 完成校验。

## 安全说明

- 易支付 **return** 与 **notify** 均校验签名；return 入账时另校验金额
- 设备管理 WebSocket（`/ws`）仅 **管理员** 可连接
- `/api/admin/config` 等管理接口需管理员权限
- 公开下单、设备上下文查询受 **限流** 约束，可在「系统配置」调整

## 本地开发

前端开发模式（`pnpm dev`）下，管理后台在 `http://127.0.0.1:3000`，API 代理到 `8000`。

本地调试支付回调时，可暂时将 `PUBLIC_BASE_URL` 设为内网穿透地址，或手动填写完整的 `notify_url` / `return_url`。

对外分享给最终用户的支付链接，应使用生产域名，而非 `localhost`。
