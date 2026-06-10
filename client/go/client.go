package authclient

import (
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"runtime"
	"strings"
	"time"

	"github.com/go-resty/resty/v2"
)

const (
	secondsPerMinute = 60
	secondsPerHour   = 3600
	secondsPerDay    = 86400
	
	heartbeatHTTPClientTimeout       = 2 * time.Second
	heartbeatHTTPDialTLSHeaderBudget = 900 * time.Millisecond
)

var heartbeatHTTPClient = &http.Client{
	Timeout: heartbeatHTTPClientTimeout,
	Transport: &http.Transport{
		Proxy:                 http.ProxyFromEnvironment,
		DialContext:           (&net.Dialer{Timeout: heartbeatHTTPDialTLSHeaderBudget}).DialContext,
		TLSHandshakeTimeout:   heartbeatHTTPDialTLSHeaderBudget,
		ResponseHeaderTimeout: heartbeatHTTPClientTimeout,
		IdleConnTimeout:       90 * time.Second,
	},
}

type AuthResult struct {
	Authorized  bool   `json:"authorized"`
	Message     string `json:"message"`
	Success     bool   `json:"success"`
	FromCache   bool   `json:"from_cache"`
	IsAuthError bool   `json:"is_auth_error,omitempty"`
	Plan        string `json:"plan,omitempty"`
}

type AuthorizationInfo struct {
	Authorized         bool    `json:"authorized"`
	Success            bool    `json:"success"`
	FromCache          bool    `json:"from_cache"`
	Message            string  `json:"message"`
	DeviceID           string  `json:"device_id"`
	ServerURL          string  `json:"server_url"`
	CacheRemainingTime string  `json:"cache_remaining_time,omitempty"`
	CacheValid         bool    `json:"cache_valid,omitempty"`
	CachedAt           float64 `json:"cached_at,omitempty"`
	CachedAtReadable   string  `json:"cached_at_readable,omitempty"`
	Plan               string  `json:"plan,omitempty"`
}

type PlanInfo struct {
	Success      bool   `json:"success"`
	Message      string `json:"message,omitempty"`
	DisplayName  string `json:"display_name,omitempty"`
	SoftwareName string `json:"software_name,omitempty"`
	AuthMode     string `json:"auth_mode,omitempty"`
	Plan         string `json:"plan,omitempty"`
	PlanLabel    string `json:"plan_label,omitempty"`
	PlanDetail   string `json:"plan_detail,omitempty"`
	Price        string `json:"price,omitempty"`
	PayType      string `json:"pay_type,omitempty"`
	CanPay       bool   `json:"can_pay,omitempty"`
}

type PaymentContext struct {
	Success      bool   `json:"success"`
	Message      string `json:"message,omitempty"`
	DeviceID     string `json:"device_id,omitempty"`
	SoftwareName string `json:"software_name,omitempty"`
	DisplayName  string `json:"display_name,omitempty"`
	AuthMode     string `json:"auth_mode,omitempty"`
	Plan         string `json:"plan,omitempty"`
	PlanLabel    string `json:"plan_label,omitempty"`
	PlanDetail   string `json:"plan_detail,omitempty"`
	Price        string `json:"price,omitempty"`
	PayType      string `json:"pay_type,omitempty"`
	CanPay       bool   `json:"can_pay,omitempty"`
}

type CacheInfo struct {
	Authorized    bool    `json:"authorized,omitempty"`
	Message       string  `json:"message,omitempty"`
	CachedAt      float64 `json:"cached_at"`
	LastSuccessAt float64 `json:"last_success_at"`
	CacheAgeDays  float64 `json:"cache_age_days"`
	CacheValid    bool    `json:"cache_valid"`
	NeedsCheck    bool    `json:"needs_check"`
	CacheFile     string  `json:"cache_file"`
}

type BackgroundRefreshHandle struct {
	Soft bool
	Done <-chan *AuthResult
}

type AuthorizationError struct {
	Message   string
	Result    *AuthResult
	DeviceID  string
	ServerURL string
}

func (e *AuthorizationError) Error() string {
	return e.Message
}

func (e *AuthorizationError) IsNetworkError() bool {
	message := e.Message
	if e.Result != nil {
		message = e.Result.Message
	}
	keywords := []string{"连接失败", "连接", "network", "timeout", "connection"}
	lowerMessage := strings.ToLower(message)
	for _, keyword := range keywords {
		if strings.Contains(lowerMessage, strings.ToLower(keyword)) {
			return true
		}
	}
	return false
}

func (e *AuthorizationError) IsUnauthorized() bool {
	if e.Result != nil {
		return !e.Result.Authorized && e.Result.Success
	}
	return strings.Contains(e.Message, "未授权") || strings.Contains(e.Message, "禁用")
}

func (e *AuthorizationError) IsValidationError() bool {
	if e.Result != nil {
		return !e.Result.Success
	}
	return strings.Contains(e.Message, "无法验证授权") || strings.Contains(e.Message, "验证失败")
}

type AuthClient struct {
	serverURL                    string
	softwareName                 string
	softwareVersion              string
	deviceID                     string
	deviceInfo                   DeviceInfo
	deviceInfoDeferred           bool 
	clientSecret                 string
	cache                        *AuthCache
	cacheValidityDays            int
	checkIntervalDays            int
	debug                        bool
	stateBundleExistedBeforeInit bool
	lastPlan                     string
	factsPrefetch                chan DeviceFacts
}

type AuthClientConfig struct {
	ServerURL         string
	SoftwareName      string
	SoftwareVersion   string
	DeviceID          string
	DeviceInfo        *DeviceInfo
	ClientSecret      string
	CacheValidityDays int
	CheckIntervalDays int
	Debug             bool
}

func NewAuthClient(config AuthClientConfig) (*AuthClient, error) {
	if config.ServerURL == "" {
		return nil, errors.New("server_url不能为空")
	}
	if config.SoftwareName == "" {
		return nil, errors.New("software_name不能为空")
	}
	if config.ClientSecret == "" {
		config.ClientSecret = os.Getenv("CLIENT_SECRET")
		if config.ClientSecret == "" {
			return nil, errors.New("client_secret未配置！请在初始化时传入（发行包中硬编码），或开发时设置环境变量CLIENT_SECRET")
		}
	}

	serverURL := NormalizeServerURL(config.ServerURL)

	client := &AuthClient{
		serverURL:         serverURL,
		softwareName:      config.SoftwareName,
		softwareVersion:   config.SoftwareVersion,
		clientSecret:      config.ClientSecret,
		cacheValidityDays: config.CacheValidityDays,
		checkIntervalDays: config.CheckIntervalDays,
		debug:             config.Debug,
	}

	if client.cacheValidityDays == 0 {
		client.cacheValidityDays = 7
	}
	if client.checkIntervalDays == 0 {
		client.checkIntervalDays = 2
	}

	storageBase := DefaultClientStorageRoot()
	_ = os.MkdirAll(storageBase, 0o755)

	statePath := BundlePath(serverURL, storageBase)
	_, statErr := os.Stat(statePath)
	statePreExisted := statErr == nil

	persistedHint := ""
	if config.DeviceID == "" {
		var err error
		persistedHint, err = LoadPersistedDeviceID(serverURL, config.SoftwareName, storageBase)
		if err != nil {
			persistedHint = ""
		}
	}
	needFactsForNewID := config.DeviceID == "" && persistedHint == ""
	var facts DeviceFacts
	if needFactsForNewID {
		facts = CollectDeviceFacts()
	}

	var err error
	client.deviceID, err = BuildDeviceID(
		serverURL,
		config.DeviceID,
		facts,
		config.SoftwareName,
		storageBase,
		persistedHint,
	)
	if err != nil {
		return nil, fmt.Errorf("构建设备ID失败: %w", err)
	}

	client.cache = NewAuthCache(
		storageBase,
		client.deviceID,
		client.serverURL,
		client.softwareName,
		client.cacheValidityDays,
		client.checkIntervalDays,
	)

	if config.DeviceInfo != nil {
		client.deviceInfo = *config.DeviceInfo
		client.deviceInfoDeferred = false
	} else if needFactsForNewID {
		client.deviceInfo = BuildDeviceInfo(facts, nil)
		client.deviceInfoDeferred = false
	} else {
		client.deviceInfo = DeviceInfo{}
		client.deviceInfoDeferred = true
		if snap, snapErr := client.cache.LoadDeviceInfoSnapshot(); snapErr == nil && snap != nil {
			client.deviceInfo = *snap
			client.deviceInfoDeferred = false
		}
	}
	client.deviceInfo.SoftwareVersion = client.softwareVersion
	client.deviceInfo.SDK = &SDKInfo{
		Language:   ClientSDKLanguage,
		SDKName:    ClientSDKName,
		SDKVersion: ClientSDKVersion,
		Runtime:    runtime.Version(),
	}

	client.stateBundleExistedBeforeInit = statePreExisted

	if client.deviceInfoDeferred {
		ch := make(chan DeviceFacts, 1)
		go func() {
			ch <- CollectDeviceFacts()
		}()
		client.factsPrefetch = ch
	}

	return client, nil
}

func (c *AuthClient) ensureFullDeviceInfo() {
	if !c.deviceInfoDeferred {
		return
	}
	var facts DeviceFacts
	if c.factsPrefetch != nil {
		facts = <-c.factsPrefetch
		c.factsPrefetch = nil
	} else {
		facts = CollectDeviceFacts()
	}
	c.deviceInfo = BuildDeviceInfo(facts, nil)
	c.deviceInfo.SoftwareVersion = c.softwareVersion
	c.deviceInfo.SDK = &SDKInfo{
		Language:   ClientSDKLanguage,
		SDKName:    ClientSDKName,
		SDKVersion: ClientSDKVersion,
		Runtime:    runtime.Version(),
	}
	c.deviceInfoDeferred = false
}

func deviceInfoPublicIPUnset(info *DeviceInfo) bool {
	if info == nil || info.Network == nil {
		return true
	}
	return strings.TrimSpace(info.Network.PublicIP) == ""
}

func (c *AuthClient) errorResult(msg string) *AuthResult {
	return &AuthResult{
		Authorized: false,
		Message:    msg,
		Success:    false,
		FromCache:  false,
	}
}

func (c *AuthClient) authErrorResult(msg string) *AuthResult {
	return &AuthResult{
		Authorized:  false,
		Message:     msg,
		Success:     false,
		FromCache:   false,
		IsAuthError: true,
	}
}

func (c *AuthClient) executeHeartbeat(di map[string]interface{}, nextHeartbeat int) *AuthResult {
	var sk map[string]interface{}
	if raw, ok := di["sdk"].(map[string]interface{}); ok && raw != nil {
		sk = raw
	} else {
		sk = map[string]interface{}{}
		di["sdk"] = sk
	}
	sk["heartbeat_times"] = nextHeartbeat

	requestData := map[string]interface{}{
		"device_id":     c.deviceID,
		"software_name": c.softwareName,
		"device_info":   di,
	}

	jsonData, err := json.Marshal(requestData)
	if err != nil {
		return c.errorResult(fmt.Sprintf("序列化请求失败: %v", err))
	}

	encrypted, err := EncryptData(jsonData, c.clientSecret)
	if err != nil {
		return c.errorResult(fmt.Sprintf("加密请求失败: %v", err))
	}

	resp, err := resty.NewWithClient(heartbeatHTTPClient).R().
		SetHeader("Content-Type", "application/json").
		SetBody(map[string]string{"encrypted_data": encrypted}).
		SetResult(map[string]interface{}{}).
		Post(fmt.Sprintf("%s/api/auth/heartbeat", c.serverURL))

	if err != nil {
		c.logDebug(fmt.Sprintf("在线订阅请求异常: %v", err))
		return c.errorResult(fmt.Sprintf("连接失败: %v", err))
	}

	if resp.StatusCode() != http.StatusOK {
		errorMsg := fmt.Sprintf("服务器错误: %d", resp.StatusCode())
		if resp.StatusCode() == http.StatusForbidden {
			var errorResp map[string]interface{}
			if err := json.Unmarshal(resp.Body(), &errorResp); err == nil {
				if detail, ok := errorResp["detail"].(string); ok {
					errorMsg = detail
				}
			}
		}
		c.logDebug(fmt.Sprintf("在线订阅失败，status=%d, message=%s", resp.StatusCode(), errorMsg))
		if resp.StatusCode() == http.StatusForbidden {
			return c.authErrorResult(errorMsg)
		}
		return c.errorResult(errorMsg)
	}

	var response map[string]interface{}
	if err := json.Unmarshal(resp.Body(), &response); err != nil {
		return c.errorResult("解析响应失败")
	}

	encryptedData, ok := response["encrypted_data"].(string)
	if !ok {
		return c.errorResult("响应格式错误")
	}

	decrypted, err := DecryptData(encryptedData, c.clientSecret)
	if err != nil {
		c.logDebug("在线订阅响应解密失败")
		return c.errorResult("解密响应失败")
	}

	var result map[string]interface{}
	if err := json.Unmarshal(decrypted, &result); err != nil {
		return c.errorResult("解析解密数据失败")
	}

	authorized, _ := result["authorized"].(bool)
	message, _ := result["message"].(string)
	if plan, ok := result["plan"].(string); ok {
		plan = strings.TrimSpace(plan)
		if plan != "" {
			c.lastPlan = plan
		}
	}

	c.logDebug(fmt.Sprintf("在线订阅成功，authorized=%v", authorized))
	authResult := &AuthResult{
		Authorized: authorized,
		Message:    message,
		Success:    true,
		FromCache:  false,
	}
	if c.lastPlan != "" {
		authResult.Plan = c.lastPlan
	}
	return authResult
}

func (c *AuthClient) checkOnlineLight(nextHeartbeat int) *AuthResult {
	c.logDebug("轻量在线订阅请求（不等待全量 device_info / 公网 IP）...")
	di := map[string]interface{}{}
	b, err := json.Marshal(&c.deviceInfo)
	if err != nil {
		return c.errorResult(fmt.Sprintf("序列化 device_info 失败: %v", err))
	}
	if err := json.Unmarshal(b, &di); err != nil {
		return c.errorResult(fmt.Sprintf("构造 device_info 映射失败: %v", err))
	}
	needSysHint := c.deviceInfo.Sys == nil
	if !needSysHint {
		needSysHint = strings.TrimSpace(c.deviceInfo.Sys.Hostname) == ""
	}
	if needSysHint {
		host, _ := os.Hostname()
		sysObj, ok := di["system"].(map[string]interface{})
		if !ok || sysObj == nil {
			sysObj = map[string]interface{}{}
			di["system"] = sysObj
		}
		if sysObj["hostname"] == nil || sysObj["hostname"] == "" {
			sysObj["hostname"] = host
		}
		if sysObj["os"] == nil || sysObj["os"] == "" {
			sysObj["os"] = runtime.GOOS
		}
	}
	return c.executeHeartbeat(di, nextHeartbeat)
}

func (c *AuthClient) checkOnline(nextHeartbeat int) *AuthResult {
	needPublicIP := c.deviceInfoDeferred || deviceInfoPublicIPUnset(&c.deviceInfo)
	pubCh := make(chan string, 1)
	go func() {
		if needPublicIP {
			pubCh <- fetchPublicIP()
		} else {
			pubCh <- ""
		}
	}()
	c.ensureFullDeviceInfo()
	pub := <-pubCh

	c.logDebug("开始在线订阅请求...")

	di := map[string]interface{}{}
	b, err := json.Marshal(c.deviceInfo)
	if err != nil {
		return c.errorResult(fmt.Sprintf("序列化 device_info 失败: %v", err))
	}
	if err := json.Unmarshal(b, &di); err != nil {
		return c.errorResult(fmt.Sprintf("构造 device_info 映射失败: %v", err))
	}
	if pub != "" {
		var netMap map[string]interface{}
		if raw, ok := di["network"].(map[string]interface{}); ok && raw != nil {
			netMap = raw
		} else {
			netMap = map[string]interface{}{}
			di["network"] = netMap
		}
		netMap["public_ip"] = pub
		if c.deviceInfo.Network == nil {
			c.deviceInfo.Network = &DeviceNetwork{}
		}
		c.deviceInfo.Network.PublicIP = pub
	}

	return c.executeHeartbeat(di, nextHeartbeat)
}

func (c *AuthClient) checkOnlineProgressive(nextHb int) *AuthResult {
	r1 := c.checkOnlineLight(nextHb)
	if r1.Success {
		if r1.Authorized {
			c.logDebug("在线订阅成功，更新缓存")
			hb := nextHb
			c.persistHeartbeatResult(r1, &hb)
			c.logDebug("轻量心跳已落盘，发起全量 device_info 补全心跳...")
			n2 := nextHb + 1
			r2 := c.checkOnline(n2)
			if r2.Success {
				c.logDebug("在线订阅成功，更新缓存")
				var hb2 *int
				if r2.Authorized {
					hb2 = &n2
				}
				c.persistHeartbeatResult(r2, hb2)
				return r2
			}
			if c.cache.IsCacheValid() {
				cd, err := c.cache.GetCache()
				if err == nil && cd != nil {
					remaining := c.formatRemainingTime(cd.LastSuccessAt)
					c.logDebug(fmt.Sprintf("补全心跳失败，沿用轻量结果，订阅剩余时间: %s", remaining))
					return &AuthResult{
						Authorized: true,
						Message:    cd.Message,
						Success:    true,
						FromCache:  true,
					}
				}
			}
			return r2
		}
		c.persistHeartbeatResult(r1, nil)
		return r1
	}
	r3 := c.checkOnline(nextHb)
	if r3.Success {
		var hb3 *int
		if r3.Authorized {
			hb3 = &nextHb
		}
		c.persistHeartbeatResult(r3, hb3)
	}
	return r3
}

func (c *AuthClient) persistHeartbeatResult(online *AuthResult, hb *int) {
	var snap *DeviceInfo
	if online.Authorized {
		snap = &c.deviceInfo
	}
	var saveErr error
	for attempt := 0; attempt < 3; attempt++ {
		saveErr = c.cache.SaveCache(online.Authorized, online.Message, hb, snap)
		if saveErr == nil {
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if saveErr != nil {
		c.logDebug(fmt.Sprintf("写入缓存失败（已重试）: %v", saveErr))
	}
}

func (c *AuthClient) CheckAuthorization(forceOnline bool) *AuthResult {
	_ = forceOnline
	if c.debug {
		cf := c.cache.cacheFile
		_, nowErr := os.Stat(cf)
		fileNow := nowErr == nil
		pre := c.stateBundleExistedBeforeInit
		desc := "不存在（持久化可能失败）"
		switch {
		case fileNow && pre:
			desc = "启动前已存在"
		case fileNow && !pre:
			desc = "启动前不存在，构造客户端时已新建（device_id 持久化）"
		case !fileNow && pre:
			desc = "启动前曾有，当前缺失（异常）"
		}
		c.logDebug(fmt.Sprintf("状态包: %s | %s", cf, desc))
	}

	cacheData, storedHb := c.cache.snapshotAuthRow()
	cacheValid := c.cache.IsCacheTTLValid(cacheData)
	if cacheValid {
		c.logDebug("本地缓存仍在有效期内（在线失败时可作后备）")
		c.logDebug("缓存有效，继续尝试在线订阅来更新订阅")
	} else {
		if cacheData != nil {
			c.logDebug("缓存存在但已过期，准备发起在线订阅请求")
		} else {
			c.logDebug("未找到缓存，准备发起在线订阅请求")
		}
	}

	nextHb := storedHb + 1
	onlineResult := c.checkOnline(nextHb)

	if onlineResult.Success {
		c.logDebug("在线订阅成功，更新缓存")
		var hb *int
		if onlineResult.Authorized {
			hb = &nextHb
		}
		c.persistHeartbeatResult(onlineResult, hb)
		return onlineResult
	}

	if cacheValid && !onlineResult.IsAuthError {
		remaining := c.formatRemainingTime(cacheData.LastSuccessAt)
		c.logDebug(fmt.Sprintf("在线订阅失败，但缓存有效，使用缓存结果，订阅剩余时间: %s", remaining))
		return &AuthResult{
			Authorized: true,
			Message:    cacheData.Message,
			Success:    true,
			FromCache:  true,
		}
	}

	if cacheData != nil {
		remaining := c.formatRemainingTime(cacheData.LastSuccessAt)
		c.logDebug(fmt.Sprintf("在线订阅失败，缓存已过期，返回失败结果，订阅剩余时间: %s", remaining))
	} else {
		c.logDebug(fmt.Sprintf("在线订阅失败，返回失败结果: %s", onlineResult.Message))
	}
	return onlineResult
}

func (c *AuthClient) CheckAuthorizationProgressive(forceOnline bool) *AuthResult {
	_ = forceOnline
	if c.debug {
		cf := c.cache.cacheFile
		_, nowErr := os.Stat(cf)
		fileNow := nowErr == nil
		pre := c.stateBundleExistedBeforeInit
		desc := "不存在（持久化可能失败）"
		switch {
		case fileNow && pre:
			desc = "启动前已存在"
		case fileNow && !pre:
			desc = "启动前不存在，构造客户端时已新建（device_id 持久化）"
		case !fileNow && pre:
			desc = "启动前曾有，当前缺失（异常）"
		}
		c.logDebug(fmt.Sprintf("状态包: %s | %s", cf, desc))
	}

	cacheData, storedHb := c.cache.snapshotAuthRow()
	cacheValid := c.cache.IsCacheTTLValid(cacheData)
	if cacheValid {
		c.logDebug("本地缓存仍在有效期内（在线失败时可作后备）")
		c.logDebug("缓存有效，继续尝试在线订阅来更新订阅")
	} else {
		if cacheData != nil {
			c.logDebug("缓存存在但已过期，准备发起在线订阅请求")
		} else {
			c.logDebug("未找到缓存，准备发起在线订阅请求")
		}
	}

	nextHb := storedHb + 1
	onlineResult := c.checkOnlineProgressive(nextHb)

	if onlineResult.Success {
		return onlineResult
	}

	if cacheValid && !onlineResult.IsAuthError {
		remaining := c.formatRemainingTime(cacheData.LastSuccessAt)
		c.logDebug(fmt.Sprintf("在线订阅失败，但缓存有效，使用缓存结果，订阅剩余时间: %s", remaining))
		return &AuthResult{
			Authorized: true,
			Message:    cacheData.Message,
			Success:    true,
			FromCache:  true,
		}
	}

	if cacheData != nil {
		remaining := c.formatRemainingTime(cacheData.LastSuccessAt)
		c.logDebug(fmt.Sprintf("在线订阅失败，缓存已过期，返回失败结果，订阅剩余时间: %s", remaining))
	} else {
		c.logDebug(fmt.Sprintf("在线订阅失败，返回失败结果: %s", onlineResult.Message))
	}
	return onlineResult
}

func (c *AuthClient) DeviceID() string {
	return c.deviceID
}

func (c *AuthClient) ServerURL() string {
	return c.serverURL
}

func (c *AuthClient) SoftwareName() string {
	return c.softwareName
}

func (c *AuthClient) SoftwareVersion() string {
	return c.softwareVersion
}

func (c *AuthClient) Debug() bool {
	return c.debug
}

func (c *AuthClient) RequireAuthorization(forceOnline bool) error {
	ok, err := c.RequireAuthorizationEx(forceOnline, true)
	if err != nil {
		return err
	}
	if !ok {
		return &AuthorizationError{
			Message:   "设备未授权",
			DeviceID:  c.deviceID,
			ServerURL: c.serverURL,
		}
	}
	return nil
}

func (c *AuthClient) RequireAuthorizationEx(forceOnline, raiseException bool) (bool, error) {
	result := c.CheckAuthorization(forceOnline)
	ok := result.Success && result.Authorized
	if ok {
		return true, nil
	}
	if raiseException {
		return false, &AuthorizationError{
			Message:   result.Message,
			Result:    result,
			DeviceID:  c.deviceID,
			ServerURL: c.serverURL,
		}
	}
	return false, nil
}

func (c *AuthClient) SubmitCheckAuthorization(forceOnline bool) <-chan *AuthResult {
	ch := make(chan *AuthResult, 1)
	go func() {
		ch <- c.CheckAuthorization(forceOnline)
	}()
	return ch
}

func (c *AuthClient) SubmitCheckAuthorizationProgressive(forceOnline bool) <-chan *AuthResult {
	ch := make(chan *AuthResult, 1)
	go func() {
		ch <- c.CheckAuthorizationProgressive(forceOnline)
	}()
	return ch
}

func (c *AuthClient) SubmitRequireAuthorization(forceOnline, raiseException bool) <-chan struct {
	OK    bool
	Error error
} {
	ch := make(chan struct {
		OK    bool
		Error error
	}, 1)
	go func() {
		ok, err := c.RequireAuthorizationEx(forceOnline, raiseException)
		ch <- struct {
			OK    bool
			Error error
		}{OK: ok, Error: err}
	}()
	return ch
}

func (c *AuthClient) CanSoftLaunch() bool {
	return c.cache.IsCacheValid()
}

func (c *AuthClient) StartBackgroundRefresh(forceOnline bool, onDone func(*AuthResult)) BackgroundRefreshHandle {
	soft := c.CanSoftLaunch()
	done := make(chan *AuthResult, 1)
	go func() {
		r := c.CheckAuthorizationProgressive(forceOnline)
		if onDone != nil {
			onDone(r)
		}
		done <- r
	}()
	return BackgroundRefreshHandle{Soft: soft, Done: done}
}

func (c *AuthClient) ClearCache() error {
	return c.cache.ClearCache()
}

func (c *AuthClient) GetPlanInfo() *PlanInfo {
	requestData := map[string]string{}
	if strings.TrimSpace(c.softwareName) != "" {
		requestData["software_name"] = c.softwareName
	}
	payload, err := json.Marshal(requestData)
	if err != nil {
		return &PlanInfo{Success: false, Message: fmt.Sprintf("序列化请求失败: %v", err)}
	}
	encrypted, err := EncryptData(payload, c.clientSecret)
	if err != nil {
		return &PlanInfo{Success: false, Message: fmt.Sprintf("加密请求失败: %v", err)}
	}

	resp, err := resty.NewWithClient(heartbeatHTTPClient).R().
		SetHeader("Content-Type", "application/json").
		SetBody(map[string]string{"encrypted_data": encrypted}).
		SetResult(map[string]interface{}{}).
		Post(fmt.Sprintf("%s/api/auth/plan-info", c.serverURL))
	if err != nil {
		return &PlanInfo{Success: false, Message: fmt.Sprintf("连接失败: %v", err)}
	}
	if resp.StatusCode() != http.StatusOK {
		errorMsg := fmt.Sprintf("服务器错误: %d", resp.StatusCode())
		if resp.StatusCode() == http.StatusForbidden {
			var errorResp map[string]interface{}
			if err := json.Unmarshal(resp.Body(), &errorResp); err == nil {
				if detail, ok := errorResp["detail"].(string); ok {
					errorMsg = detail
				}
			}
		}
		return &PlanInfo{Success: false, Message: errorMsg}
	}

	var envelope map[string]interface{}
	if err := json.Unmarshal(resp.Body(), &envelope); err != nil {
		return &PlanInfo{Success: false, Message: "解析响应失败"}
	}
	encryptedData, ok := envelope["encrypted_data"].(string)
	if !ok || encryptedData == "" {
		return &PlanInfo{Success: false, Message: "响应格式错误"}
	}
	decrypted, err := DecryptData(encryptedData, c.clientSecret)
	if err != nil {
		return &PlanInfo{Success: false, Message: "解密响应失败"}
	}

	info := &PlanInfo{Success: true}
	if err := json.Unmarshal(decrypted, info); err != nil {
		return &PlanInfo{Success: false, Message: "解析解密数据失败"}
	}
	info.Success = true
	return info
}

func (c *AuthClient) GetPaymentContext() *PaymentContext {
	resp, err := resty.NewWithClient(heartbeatHTTPClient).R().
		SetQueryParam("device_id", c.deviceID).
		SetResult(map[string]interface{}{}).
		Get(fmt.Sprintf("%s/api/payment/device-context", c.serverURL))
	if err != nil {
		return &PaymentContext{Success: false, Message: fmt.Sprintf("连接失败: %v", err)}
	}
	if resp.StatusCode() != http.StatusOK {
		return &PaymentContext{Success: false, Message: fmt.Sprintf("服务器错误: %d", resp.StatusCode())}
	}

	ctx := &PaymentContext{Success: true}
	if err := json.Unmarshal(resp.Body(), ctx); err != nil {
		return &PaymentContext{Success: false, Message: "解析响应失败"}
	}
	ctx.Success = true
	return ctx
}

func (c *AuthClient) GetCacheInfo() *CacheInfo {
	cache, err := c.cache.GetCache()
	if err != nil || cache == nil {
		return nil
	}
	now := float64(time.Now().UnixNano()) / 1e9
	return &CacheInfo{
		Authorized:    true,
		Message:       cache.Message,
		CachedAt:      cache.LastSuccessAt,
		LastSuccessAt: cache.LastSuccessAt,
		CacheAgeDays:  (now - cache.LastSuccessAt) / secondsPerDay,
		CacheValid:    c.cache.IsCacheValid(),
		NeedsCheck:    c.cache.NeedsCheck(),
		CacheFile:     c.cache.cacheFile,
	}
}

func (c *AuthClient) GetAuthorizationInfo() *AuthorizationInfo {
	cache, err := c.cache.GetCache()
	var info *AuthorizationInfo
	if err == nil && cache != nil {
		info = &AuthorizationInfo{
			Authorized:    true,
			Success:         true,
			FromCache:       true,
			Message:         cache.Message,
			DeviceID:        c.deviceID,
			ServerURL:       c.serverURL,
			CachedAt:        cache.LastSuccessAt,
			CacheRemainingTime: c.formatRemainingTime(cache.LastSuccessAt),
			CacheValid:      c.cache.IsCacheValid(),
		}
		if cache.LastSuccessAt > 0 {
			info.CachedAtReadable = time.Unix(int64(cache.LastSuccessAt), 0).Format("2006-01-02 15:04:05")
		}
	} else {
		info = &AuthorizationInfo{
			Authorized:    false,
			Success:         false,
			FromCache:       false,
			Message:         "无本地授权缓存",
			DeviceID:        c.deviceID,
			ServerURL:       c.serverURL,
			CacheRemainingTime: "无缓存",
			CacheValid:      false,
		}
	}

	if c.lastPlan != "" {
		info.Plan = c.lastPlan
	}

	if c.debug {
		if b, err := json.MarshalIndent(info, "", "  "); err == nil {
			c.logDebug("授权信息摘要:\n" + string(b))
		}
	}

	return info
}

func (c *AuthClient) logDebug(msg string) {
	if c.debug {
		fmt.Printf("[go][DEBUG] %s\n", msg)
	}
}

func (c *AuthClient) formatRemainingTime(cachedAt float64) string {
	if cachedAt <= 0 {
		return "未知"
	}

	now := float64(time.Now().UnixNano()) / 1e9
	elapsed := now - cachedAt
	remaining := float64(c.cache.cacheValiditySeconds) - elapsed

	if remaining <= 0 {
		return "已过期"
	}

	days := int(remaining / secondsPerDay)
	hours := int((remaining - float64(days*secondsPerDay)) / secondsPerHour)
	minutes := int((remaining - float64(days*secondsPerDay) - float64(hours*secondsPerHour)) / secondsPerMinute)

	var parts []string
	if days > 0 {
		parts = append(parts, fmt.Sprintf("%d天", days))
	}
	if hours > 0 {
		parts = append(parts, fmt.Sprintf("%d小时", hours))
	}
	if minutes > 0 || len(parts) == 0 {
		parts = append(parts, fmt.Sprintf("%d分钟", minutes))
	}

	return strings.Join(parts, "")
}
