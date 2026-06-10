package authclient

import (
	"net/http"
	"testing"
	"time"
)

func TestResolveTimeoutUsesFallbackWhenZero(t *testing.T) {
	got := resolveTimeout(0, defaultPlanInfoTimeout)
	if got != defaultPlanInfoTimeout {
		t.Fatalf("resolveTimeout(0) = %v, want %v", got, defaultPlanInfoTimeout)
	}
}

func TestResolveTimeoutUsesExplicitValue(t *testing.T) {
	custom := 15 * time.Second
	got := resolveTimeout(custom, defaultPlanInfoTimeout)
	if got != custom {
		t.Fatalf("resolveTimeout(custom) = %v, want %v", got, custom)
	}
}

func TestDialTLSBudgetForShortRequest(t *testing.T) {
	got := dialTLSBudgetFor(3 * time.Second)
	if got != 3*time.Second {
		t.Fatalf("dialTLSBudgetFor(3s) = %v, want 3s", got)
	}
}

func TestDialTLSBudgetForLongRequest(t *testing.T) {
	got := dialTLSBudgetFor(10 * time.Second)
	if got != maxDialTLSBudget {
		t.Fatalf("dialTLSBudgetFor(10s) = %v, want %v", got, maxDialTLSBudget)
	}
}

func TestBuildHTTPClientDefaults(t *testing.T) {
	client := buildHTTPClient(0)
	if client.Timeout != defaultHeartbeatTimeout {
		t.Fatalf("client.Timeout = %v, want %v", client.Timeout, defaultHeartbeatTimeout)
	}
	transport, ok := client.Transport.(*http.Transport)
	if !ok {
		t.Fatal("expected *http.Transport")
	}
	if transport.TLSHandshakeTimeout != 3*time.Second {
		t.Fatalf("TLSHandshakeTimeout = %v, want 3s", transport.TLSHandshakeTimeout)
	}
	if transport.ResponseHeaderTimeout != defaultHeartbeatTimeout {
		t.Fatalf("ResponseHeaderTimeout = %v, want %v", transport.ResponseHeaderTimeout, defaultHeartbeatTimeout)
	}
}

func TestIsTimeoutMessage(t *testing.T) {
	cases := []struct {
		msg  string
		want bool
	}{
		{"连接失败: Get \"https://x\": net/http: timeout awaiting response headers", true},
		{"连接失败: dial tcp: i/o timeout", true},
		{"连接失败: connection refused", false},
		{"服务器错误: 500", false},
	}
	for _, tc := range cases {
		if got := isTimeoutMessage(tc.msg); got != tc.want {
			t.Fatalf("isTimeoutMessage(%q) = %v, want %v", tc.msg, got, tc.want)
		}
	}
}
