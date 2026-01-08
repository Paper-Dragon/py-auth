# py-auth-client-go

Go语言版本的授权客户端，用于检查设备授权状态，支持缓存和AES加密传输。

## 功能特性

- ✅ 设备授权状态检查
- ✅ 本地缓存机制（7天有效期）
- ✅ AES加密传输
- ✅ 自动设备信息收集
- ✅ 离线缓存支持
- ✅ 跨平台支持（Windows、macOS、Linux）

## 安装

```bash
go get github.com/Paper-Dragon/py-auth/client/go
```

## 快速开始

```go
package main

import (
    "fmt"
    "log"
    
    authclient "github.com/Paper-Dragon/py-auth/client/go"
)

func main() {
    // 初始化客户端
    client, err := authclient.NewAuthClient(authclient.AuthClientConfig{
        ServerURL:         "http://localhost:8000",
        SoftwareName:      "我的软件",
        ClientSecret:      "your-client-secret-key-change-in-production",
        EnableCache:       true,
        CacheValidityDays: 7,
        CheckIntervalDays: 2,
    })
    
    if err != nil {
        log.Fatalf("初始化客户端失败: %v", err)
    }

    // 检查授权
    err = client.RequireAuthorization()
    if err != nil {
        if authErr, ok := err.(*authclient.AuthorizationError); ok {
            fmt.Printf("❌ 授权失败: %s\n", authErr.Message)
            os.Exit(1)
        }
    }

    fmt.Println("✅ 设备已授权")
}
```

## 配置

### 必需参数

- `ServerURL`: 授权服务器地址
- `SoftwareName`: 软件名称（必填）
- `ClientSecret`: 客户端密钥（必须与服务端一致），也可以通过环境变量 `CLIENT_SECRET` 设置

### 可选参数

- `DeviceID`: 设备ID（不提供则自动生成）
- `DeviceInfo`: 设备信息（不提供则自动收集）
- `CacheDir`: 缓存目录（默认使用系统隐藏目录）
- `EnableCache`: 是否启用缓存（默认true）
- `CacheValidityDays`: 缓存有效期（天，默认7天）
- `CheckIntervalDays`: 检查间隔（天，默认2天）
- `Debug`: 是否输出调试日志（默认false）

## 缓存机制

- 缓存有效期：7天
- 始终向服务端发送请求并更新本地缓存
- 在线验证失败时，在有效期内使用缓存作为后备
- 缓存文件经过混淆加密，隐藏在系统目录中

## API 文档

### AuthClient

主要的客户端结构体。

#### NewAuthClient

创建新的授权客户端。

```go
client, err := authclient.NewAuthClient(authclient.AuthClientConfig{
    ServerURL:    "http://localhost:8000",
    SoftwareName: "我的软件",
    ClientSecret: "your-secret",
})
```

#### CheckAuthorization

检查设备授权状态（带缓存）。

```go
result := client.CheckAuthorization()
if result.Success && result.Authorized {
    fmt.Println("设备已授权")
}
```

#### RequireAuthorization

要求授权，如果未授权则返回错误。

```go
err := client.RequireAuthorization()
if err != nil {
    // 处理错误
}
```

#### GetAuthorizationInfo

获取授权信息（用户友好的格式）。

```go
info := client.GetAuthorizationInfo()
fmt.Printf("授权状态: %v\n", info.Authorized)
fmt.Printf("剩余时间: %s\n", info.RemainingTime)
```

#### ClearCache

清除本地缓存。

```go
err := client.ClearCache()
```

### AuthorizationError

授权错误类型，实现了 `error` 接口。

#### 方法

- `IsNetworkError() bool`: 判断是否为网络错误
- `IsUnauthorized() bool`: 判断是否为未授权错误
- `IsValidationError() bool`: 判断是否为验证错误

## 使用示例

### 基本使用

```go
client, _ := authclient.NewAuthClient(authclient.AuthClientConfig{
    ServerURL:    "http://localhost:8000",
    SoftwareName: "我的软件",
    ClientSecret: os.Getenv("CLIENT_SECRET"),
})

err := client.RequireAuthorization()
if err != nil {
    log.Fatal(err)
}
```

### 错误处理

```go
err := client.RequireAuthorization()
if err != nil {
    if authErr, ok := err.(*authclient.AuthorizationError); ok {
        if authErr.IsNetworkError() {
            fmt.Println("网络连接错误，请检查网络")
        } else if authErr.IsUnauthorized() {
            fmt.Println("设备未授权，请联系管理员")
        } else if authErr.IsValidationError() {
            fmt.Println("验证失败，请检查配置")
        }
    }
}
```

### 自定义设备信息

```go
client, _ := authclient.NewAuthClient(authclient.AuthClientConfig{
    ServerURL:    "http://localhost:8000",
    SoftwareName: "我的软件",
    ClientSecret: "your-secret",
    DeviceInfo: &authclient.DeviceInfo{
        Hostname: "custom-hostname",
        // ... 其他字段
    },
})
```

### 禁用缓存

```go
client, _ := authclient.NewAuthClient(authclient.AuthClientConfig{
    ServerURL:    "http://localhost:8000",
    SoftwareName: "我的软件",
    ClientSecret: "your-secret",
    EnableCache:  false,
})
```

## 网络传输

- 使用AES加密保护请求和响应数据
- 加密密钥基于 `CLIENT_SECRET` 生成
- 必须与服务端的 `CLIENT_SECRET` 保持一致

## 设备ID

- 设备ID基于硬件信息（MAC地址、磁盘ID、CPU、内存等）和软件名称生成
- 同一台电脑上的不同软件会有不同的设备ID
- 设备ID会持久化到本地文件，下次启动时复用

## 兼容性

与 Python 版本的客户端完全兼容，可以：
- 使用相同的服务器
- 共享相同的 `CLIENT_SECRET`
- 使用相同的缓存机制

## 许可证

与主项目保持一致
