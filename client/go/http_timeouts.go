package authclient

import (
	"net"
	"net/http"
	"strings"
	"time"
)

const (
	defaultHeartbeatTimeout      = 3 * time.Second
	defaultPlanInfoTimeout       = 10 * time.Second
	defaultPaymentContextTimeout = 10 * time.Second
	maxDialTLSBudget             = 5 * time.Second
)

func resolveTimeout(value, fallback time.Duration) time.Duration {
	if value > 0 {
		return value
	}
	return fallback
}

func dialTLSBudgetFor(requestTimeout time.Duration) time.Duration {
	if requestTimeout <= 0 {
		return maxDialTLSBudget
	}
	budget := requestTimeout
	if budget > maxDialTLSBudget {
		budget = maxDialTLSBudget
	}
	return budget
}

func buildHTTPClient(requestTimeout time.Duration) *http.Client {
	timeout := resolveTimeout(requestTimeout, defaultHeartbeatTimeout)
	dialBudget := dialTLSBudgetFor(timeout)
	return &http.Client{
		Timeout: timeout,
		Transport: &http.Transport{
			Proxy:                 http.ProxyFromEnvironment,
			DialContext:           (&net.Dialer{Timeout: dialBudget}).DialContext,
			TLSHandshakeTimeout:   dialBudget,
			ResponseHeaderTimeout: timeout,
			IdleConnTimeout:       90 * time.Second,
		},
	}
}

func isTimeoutMessage(message string) bool {
	lower := strings.ToLower(message)
	return strings.Contains(lower, "timeout") ||
		strings.Contains(message, "超时") ||
		strings.Contains(lower, "deadline exceeded") ||
		strings.Contains(lower, "context deadline")
}
