package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	authclient "github.com/Paper-Dragon/py-auth/client/go"
)

func clientSecret() string {
	_, file, _, _ := runtime.Caller(0)
	data, _ := os.ReadFile(filepath.Clean(filepath.Join(filepath.Dir(file), "..", "..", "..", ".env")))
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, val, _ := strings.Cut(line, "=")
		if strings.TrimSpace(key) != "CLIENT_SECRET" {
			continue
		}
		return strings.Trim(strings.TrimSpace(val), `"'`)
	}
	return ""
}

func main() {
	secret := clientSecret()
	if secret == "" {
		fmt.Fprintln(os.Stderr, "缺少 CLIENT_SECRET")
		os.Exit(1)
	}

	cfg := authclient.AuthClientConfig{
		ServerURL:         "http://localhost:8000",
		SoftwareName:      "软件go示例",
		SoftwareVersion:   "0.0.1",
		ClientSecret:      secret,
		CacheValidityDays: 7,
		CheckIntervalDays: 2,
		Debug:             true,
	}
	client, err := authclient.NewAuthClient(cfg)
	if err != nil {
		log.Fatalf("初始化客户端失败: %v", err)
	}

	fmt.Println("（模拟）界面/初始化已继续，后台刷新授权…")

	onRefresh := func(r *authclient.AuthResult) {
		if r != nil && r.Success && r.Authorized {
			fmt.Println("后台刷新：仍授权")
		} else if r != nil {
			fmt.Fprintf(os.Stderr, "后台刷新：%s（可在此禁用功能）\n", r.Message)
		}
	}

	handle := client.StartBackgroundRefresh(false, onRefresh)
	if handle.Soft {
		fmt.Printf("产品 %s: 可先依据本地快照启动\n", client.SoftwareName())
	} else {
		fmt.Printf("产品 %s: 无有效本地快照，需等待本次检查结果\n", client.SoftwareName())
	}

	r := <-handle.Done
	if !handle.Soft && (r == nil || !r.Success || !r.Authorized) {
		msg := "失败"
		if r != nil {
			msg = r.Message
		}
		fmt.Fprintf(os.Stderr, "未授权: %s\n", msg)
		os.Exit(1)
	}
	if handle.Soft && (r == nil || !r.Success || !r.Authorized) {
		msg := "失败"
		if r != nil {
			msg = r.Message
		}
		fmt.Fprintf(os.Stderr, "警告：本地曾放行但刷新失败: %s\n", msg)
	}

	fmt.Println("✅ 全部产品授权有效（含后台刷新结果）")
	info := client.GetAuthorizationInfo()
	if !cfg.Debug {
		if b, err := json.MarshalIndent(info, "", "  "); err == nil {
			fmt.Println(string(b))
		}
	}
}
