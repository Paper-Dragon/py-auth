package authclient

import (
	"bytes"
	"compress/zlib"
	"crypto/md5"
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"
)

// CacheData 缓存数据结构
type CacheData struct {
	Authorized bool    `json:"a"`
	Message    string  `json:"m"`
	CachedAt   float64 `json:"c"`
	LastCheck  float64 `json:"l"`
}

// AuthCache 授权缓存管理
type AuthCache struct {
	cacheDir            string
	cacheFile           string
	deviceID            string
	serverURL           string
	softwareName        string
	encryptKey          []byte
	cacheValidityDays   int
	cacheValiditySeconds int64
	checkIntervalDays   int
	checkIntervalSeconds int64
}

// NewAuthCache 创建新的缓存管理器
func NewAuthCache(cacheDir, deviceID, serverURL, softwareName string, cacheValidityDays, checkIntervalDays int) *AuthCache {
	cache := &AuthCache{
		deviceID:            deviceID,
		serverURL:           serverURL,
		softwareName:        softwareName,
		cacheValidityDays:   cacheValidityDays,
		checkIntervalDays:   checkIntervalDays,
	}
	
	cache.cacheValiditySeconds = int64(cacheValidityDays * 24 * 60 * 60)
	cache.checkIntervalSeconds = int64(checkIntervalDays * 24 * 60 * 60)
	
	// 确定缓存目录
	if cacheDir != "" {
		cache.cacheDir = cacheDir
	} else {
		home, _ := os.UserHomeDir()
		switch runtime.GOOS {
		case "windows":
			localAppData := os.Getenv("LOCALAPPDATA")
			if localAppData == "" {
				localAppData = filepath.Join(home, "AppData", "Local")
			}
			cache.cacheDir = filepath.Join(localAppData, "Microsoft", "CLR_v4.0")
		case "darwin":
			cache.cacheDir = filepath.Join(home, "Library", "Caches", ".com.apple.metadata")
		default:
			cache.cacheDir = filepath.Join(home, ".cache", ".fontconfig")
		}
	}
	
	os.MkdirAll(cache.cacheDir, 0755)
	
	// 生成缓存文件名
	cacheKey := fmt.Sprintf("%s:%s", deviceID, softwareName)
	hash := md5.Sum([]byte(cacheKey))
	cacheFilename := fmt.Sprintf("runtime_%s.dat", fmt.Sprintf("%x", hash)[:12])
	cache.cacheFile = filepath.Join(cache.cacheDir, cacheFilename)
	
	// 生成加密密钥
	encryptMaterial := fmt.Sprintf("%s:%s:%s:obfuscate_v1", serverURL, deviceID, softwareName)
	hash256 := sha256.Sum256([]byte(encryptMaterial))
	cache.encryptKey = hash256[:]
	
	return cache
}

// obfuscate 混淆数据
func (c *AuthCache) obfuscate(data []byte) ([]byte, error) {
	// 1. 压缩数据
	var compressed bytes.Buffer
	w := zlib.NewWriter(&compressed)
	if _, err := w.Write(data); err != nil {
		return nil, err
	}
	w.Close()
	compressedBytes := compressed.Bytes()
	
	// 2. XOR混淆
	key := c.encryptKey
	keyLen := len(key)
	xored := make([]byte, len(compressedBytes))
	for i := range compressedBytes {
		xored[i] = compressedBytes[i] ^ key[i%keyLen]
	}
	
	// 3. 添加随机前缀
	timeSeed := time.Now().Unix() / 3600
	prefixMaterial := fmt.Sprintf("%s:%s:%d", c.deviceID, c.softwareName, timeSeed)
	prefixHash := md5.Sum([]byte(prefixMaterial))
	prefixSeed := prefixHash[:4]
	
	// 4. 打包：前缀(4) + 长度(4) + 数据
	packed := make([]byte, 8+len(xored))
	copy(packed[0:4], prefixSeed)
	binary.BigEndian.PutUint32(packed[4:8], uint32(len(xored)))
	copy(packed[8:], xored)
	
	// 5. 再次XOR整体
	finalKey := sha256.Sum256(append(c.encryptKey, prefixSeed...))
	final := make([]byte, len(packed))
	for i := range packed {
		final[i] = packed[i] ^ finalKey[i%len(finalKey)]
	}
	
	return final, nil
}

// deobfuscate 解除混淆
func (c *AuthCache) deobfuscate(data []byte) ([]byte, error) {
	if len(data) < 8 {
		return nil, fmt.Errorf("数据长度不足")
	}
	
	currentHour := time.Now().Unix() / 3600
	maxOffset := int64(c.cacheValidityDays*24 + 12)
	
	for hourOffset := -maxOffset; hourOffset <= maxOffset; hourOffset++ {
		timeSeed := currentHour + hourOffset
		prefixMaterial := fmt.Sprintf("%s:%s:%d", c.deviceID, c.softwareName, timeSeed)
		prefixHash := md5.Sum([]byte(prefixMaterial))
		prefixSeed := prefixHash[:4]
		
		// 1. 解除最外层XOR
		finalKey := sha256.Sum256(append(c.encryptKey, prefixSeed...))
		unpacked := make([]byte, len(data))
		for i := range data {
			unpacked[i] = data[i] ^ finalKey[i%len(finalKey)]
		}
		
		// 2. 验证前缀
		if !bytes.Equal(unpacked[0:4], prefixSeed) {
			continue
		}
		
		// 3. 解包长度和数据
		length := binary.BigEndian.Uint32(unpacked[4:8])
		if int(length) > len(unpacked)-8 {
			continue
		}
		
		xored := unpacked[8 : 8+length]
		
		// 4. 解除XOR混淆
		key := c.encryptKey
		keyLen := len(key)
		compressed := make([]byte, len(xored))
		for i := range xored {
			compressed[i] = xored[i] ^ key[i%keyLen]
		}
		
		// 5. 解压
		r, err := zlib.NewReader(bytes.NewReader(compressed))
		if err != nil {
			continue
		}
		var original bytes.Buffer
		_, err = original.ReadFrom(r)
		r.Close()
		if err != nil {
			continue
		}
		
		return original.Bytes(), nil
	}
	
	return nil, fmt.Errorf("解密失败")
}

// GetCache 获取缓存数据
func (c *AuthCache) GetCache() (*CacheData, error) {
	if _, err := os.Stat(c.cacheFile); os.IsNotExist(err) {
		return nil, nil
	}
	
	encryptedData, err := os.ReadFile(c.cacheFile)
	if err != nil {
		return nil, err
	}
	
	decrypted, err := c.deobfuscate(encryptedData)
	if err != nil {
		return nil, err
	}
	
	var cacheData CacheData
	if err := json.Unmarshal(decrypted, &cacheData); err != nil {
		return nil, err
	}
	
	return &cacheData, nil
}

// SaveCache 保存缓存数据
func (c *AuthCache) SaveCache(authorized bool, message string) error {
	now := float64(time.Now().Unix())
	cacheData := CacheData{
		Authorized: authorized,
		Message:    message,
		CachedAt:   now,
		LastCheck:  now,
	}
	
	jsonData, err := json.Marshal(cacheData)
	if err != nil {
		return err
	}
	
	encrypted, err := c.obfuscate(jsonData)
	if err != nil {
		return err
	}
	
	os.MkdirAll(c.cacheDir, 0755)
	
	err = os.WriteFile(c.cacheFile, encrypted, 0644)
	if err != nil {
		// 尝试删除后重新创建
		if _, statErr := os.Stat(c.cacheFile); statErr == nil {
			os.Remove(c.cacheFile)
			err = os.WriteFile(c.cacheFile, encrypted, 0644)
		}
		if err != nil {
			return err
		}
	}
	
	// Windows下隐藏文件
	if runtime.GOOS == "windows" {
		// 使用attrib命令隐藏文件
		cmd := exec.Command("attrib", "+H", c.cacheFile)
		cmd.Run()
	}
	
	return nil
}

// IsCacheValid 检查缓存是否有效
func (c *AuthCache) IsCacheValid() bool {
	cache, err := c.GetCache()
	if err != nil || cache == nil {
		return false
	}
	
	elapsed := time.Now().Unix() - int64(cache.CachedAt)
	return elapsed < c.cacheValiditySeconds
}

// NeedsCheck 检查是否需要在线验证
func (c *AuthCache) NeedsCheck() bool {
	cache, err := c.GetCache()
	if err != nil || cache == nil {
		return true
	}
	
	elapsed := time.Now().Unix() - int64(cache.LastCheck)
	return elapsed >= c.checkIntervalSeconds
}

// ClearCache 清除缓存
func (c *AuthCache) ClearCache() error {
	if _, err := os.Stat(c.cacheFile); os.IsNotExist(err) {
		return nil
	}
	return os.Remove(c.cacheFile)
}

