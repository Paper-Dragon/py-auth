# Go 客户端 SDK

## 依赖关系

| 文档 | 说明 |
|------|------|
| [client/README.md](../README.md) | SDK 总览与三端方法对照 |
| [docs/dev/client-storage.md](../../docs/dev/client-storage.md) | 存储、状态文件、加解密与 `device_id` 约定 |
| [docs/dev/payment.md](../../docs/dev/payment.md) | 付费授权与公开支付页 |

## 安装

```bash
go get github.com/Paper-Dragon/py-auth/client/go
```

## `AuthClientConfig` 字段

| 字段 | 是否必需 | 说明 |
|------|----------|------|
| `ServerURL` | 必填 | 服务地址 |
| `SoftwareName` | 必填 | 产品名称 |
| `SoftwareVersion` | 可选 | 软件版本 |
| `DeviceID` | 可选 | 省略时自动生成或复用 |
| `DeviceInfo` | 可选 | 为 `nil` 时自动采集 |
| `ClientSecret` | 条件必填 | 可信接入标识，硬编码在发行包；服务端信任该值确定套餐 plan。开发时可用 `CLIENT_SECRET` |
| `CacheValidityDays` | 可选 | 默认 `7`，建议传正整数；`0` 使用默认值 |
| `CheckIntervalDays` | 可选 | 默认 `2`，建议传正整数；`0` 使用默认值 |
| `Debug` | 可选 | 是否输出调试日志 |
| `HeartbeatTimeout` | 可选 | 心跳 `POST /api/auth/heartbeat` 总超时；`0` 为默认 `3s` |
| `PlanInfoTimeout` | 可选 | 套餐查询 `POST /api/auth/plan-info` 总超时；`0` 为默认 `10s` |
| `PaymentContextTimeout` | 可选 | 付费上下文 `GET /api/payment/device-context` 总超时；`0` 为默认 `10s` |

弱网或跨洋 HTTPS 时，可为 `PlanInfoTimeout` / `PaymentContextTimeout` 适当加大（如 `15 * time.Second`），心跳保持较短以免阻塞启动。

## 示例

### 启动时要求授权通过

```go
package main

import (
	"log"

	authclient "github.com/Paper-Dragon/py-auth/client/go"
)

func main() {
	c, err := authclient.NewAuthClient(authclient.AuthClientConfig{
		ServerURL:    "http://localhost:8000",
		SoftwareName: "我的软件",
		ClientSecret: "your-secret",
	})
	if err != nil {
		log.Fatal(err)
	}
	if err := c.RequireAuthorization(false); err != nil {
		log.Fatal(err)
	}
}
```

### 检查授权并按结果处理

```go
r := c.CheckAuthorization(false)
if r != nil && r.Success && r.Authorized {
	// 已授权
} else if r != nil {
	// 未授权或校验失败：r.Message
}
```

### 仅读取本地授权信息

```go
info := c.GetAuthorizationInfo()
if info != nil {
	// info.Authorized, info.Message, info.DeviceID, info.CacheRemainingTime
}
```

### 要求授权（不抛异常）

```go
ok, _ := c.RequireAuthorizationEx(false, false)
```

### 后台刷新授权

```go
handle := c.StartBackgroundRefresh(false, func(r *authclient.AuthResult) {
	// 刷新完成回调
})
r := <-handle.Done
_ = handle.Soft
_ = r
```

### 读取缓存详情

```go
cache := c.GetCacheInfo()
```

### 查询套餐信息

```go
plan := c.GetPlanInfo()
if plan != nil && plan.Success {
	fmt.Println(plan.Plan, plan.Price)
	if plan.PlanDetail != "" {
		fmt.Println(plan.PlanDetail)
	}
}

ctx := c.GetPaymentContext()
if ctx != nil && ctx.Success {
	fmt.Println(ctx.Plan, ctx.CanPay)
}
```

`GetPlanInfo()` 返回产品套餐配置（档位、价格、详情等），不表示本机是否已付款。心跳返回的 `Authorized` 表示能否上线；`Plan` 表示当前生效档位。

### 清除本地缓存

```go
if err := c.ClearCache(); err != nil {
	log.Fatal(err)
}
```
