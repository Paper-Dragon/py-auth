package main

import (
	"bufio"
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

func buildPayURL(client *authclient.AuthClient, autoPay bool) string {
	url := fmt.Sprintf("%s/pay?device_id=%s", client.ServerURL(), client.DeviceID())
	if autoPay {
		url += "&auto_pay=1"
	}
	return url
}

func guidePayment(client *authclient.AuthClient) {
	if planInfo := client.GetPlanInfo(); planInfo != nil && planInfo.Success {
		label := planInfo.PlanLabel
		if label == "" {
			label = planInfo.Plan
		}
		if label == "" {
			label = "未知套餐"
		}
		if planInfo.Price != "" {
			fmt.Printf("当前套餐：%s，价格：¥%s\n", label, planInfo.Price)
		} else {
			fmt.Printf("当前套餐：%s\n", label)
		}
		if planInfo.PlanDetail != "" {
			fmt.Printf("套餐详情：%s\n", planInfo.PlanDetail)
		}
	}

	fmt.Println("设备未授权，请在浏览器打开以下链接完成付款：")
	fmt.Printf("  %s\n", buildPayURL(client, true))

	fmt.Print("付款完成后按回车继续...")
	_, _ = bufio.NewReader(os.Stdin).ReadBytes('\n')

	if ok, _ := client.RequireAuthorizationEx(true, false); ok {
		fmt.Println("付款成功，已授权")
	} else {
		fmt.Println("仍未授权，请确认订单状态后重试")
	}
}

func main() {
	cfg := authclient.AuthClientConfig{
		ServerURL:         "http://localhost:8000",
		SoftwareName:      "软件go示例",
		SoftwareVersion:   "0.0.1",
		ClientSecret:      clientSecret(),
		CacheValidityDays: 7,
		CheckIntervalDays: 2,
		Debug:             true,
	}
	client, err := authclient.NewAuthClient(cfg)
	if err != nil {
		log.Fatalf("初始化客户端失败: %v", err)
	}

	if ok, _ := client.RequireAuthorizationEx(true, false); ok {
		fmt.Println("已授权，正常启动")
	} else {
		guidePayment(client)
	}

	info := client.GetAuthorizationInfo()
	if !cfg.Debug {
		if b, err := json.MarshalIndent(info, "", "  "); err == nil {
			fmt.Println(string(b))
		}
	}
}
