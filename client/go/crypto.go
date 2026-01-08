package authclient

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/sha512"
	"encoding/base64"
	"errors"
	"time"
)

const (
	// Fernet 常量
	version      = byte(0x80)
	timestampLen = 8
	nonceLen     = 16
	hmacLen      = 32
	overhead     = 1 + timestampLen + nonceLen + hmacLen
)

// initKey 初始化密钥（与Python兼容）
func initKey(clientSecret string) (string, error) {
	if clientSecret == "" {
		return "", errors.New("client_secret不能为空")
	}
	
	// 使用CLIENT_SECRET的SHA256哈希作为密钥
	hash := sha256.Sum256([]byte(clientSecret))
	
	// Fernet使用URL-safe base64编码的32字节密钥（与Python的base64.urlsafe_b64encode兼容）
	keyBytes := base64.URLEncoding.EncodeToString(hash[:32])
	return keyBytes, nil
}

// deriveKeys 从主密钥派生签名和加密密钥
func deriveKeys(keyStr string) (signKey, encKey []byte, err error) {
	// 解码base64密钥
	key, err := base64.URLEncoding.DecodeString(keyStr)
	if err != nil {
		return nil, nil, err
	}
	
	h := sha512.New()
	h.Write([]byte("sign"))
	h.Write(key)
	signKey = h.Sum(nil)[:32]
	
	h.Reset()
	h.Write([]byte("encrypt"))
	h.Write(key)
	encKey = h.Sum(nil)[:32]
	return
}

// EncryptData 加密数据（兼容Python Fernet）
func EncryptData(data []byte, clientSecret string) (string, error) {
	key, err := initKey(clientSecret)
	if err != nil {
		return "", err
	}
	
	signKey, encKey, err := deriveKeys(key)
	if err != nil {
		return "", err
	}
	
	// 生成随机nonce
	nonce := make([]byte, nonceLen)
	if _, err := rand.Read(nonce); err != nil {
		return "", err
	}
	
	// 获取当前时间戳
	timestamp := time.Now().Unix()
	timestampBytes := make([]byte, timestampLen)
	for i := timestampLen - 1; i >= 0; i-- {
		timestampBytes[i] = byte(timestamp & 0xff)
		timestamp >>= 8
	}
	
	// AES-128-CBC加密
	block, err := aes.NewCipher(encKey)
	if err != nil {
		return "", err
	}
	
	// PKCS7填充
	padding := aes.BlockSize - len(data)%aes.BlockSize
	paddedData := make([]byte, len(data)+padding)
	copy(paddedData, data)
	for i := len(data); i < len(paddedData); i++ {
		paddedData[i] = byte(padding)
	}
	
	// 使用nonce作为IV的前16字节
	iv := make([]byte, aes.BlockSize)
	copy(iv, nonce)
	
	mode := cipher.NewCBCEncrypter(block, iv)
	ciphertext := make([]byte, len(paddedData))
	mode.CryptBlocks(ciphertext, paddedData)
	
	// 构建消息：version + timestamp + IV + ciphertext
	message := make([]byte, 0, 1+timestampLen+nonceLen+len(ciphertext))
	message = append(message, version)
	message = append(message, timestampBytes...)
	message = append(message, nonce...)
	message = append(message, ciphertext...)
	
	// 计算HMAC
	mac := hmac.New(sha256.New, signKey)
	mac.Write(message)
	signature := mac.Sum(nil)
	
	// 最终消息：message + signature
	final := append(message, signature...)
	
	// Base64编码
	return base64.URLEncoding.EncodeToString(final), nil
}

// DecryptData 解密数据（兼容Python Fernet）
func DecryptData(encryptedData string, clientSecret string) ([]byte, error) {
	key, err := initKey(clientSecret)
	if err != nil {
		return nil, err
	}
	
	signKey, encKey, err := deriveKeys(key)
	if err != nil {
		return nil, err
	}
	
	// Base64解码
	data, err := base64.URLEncoding.DecodeString(encryptedData)
	if err != nil {
		return nil, err
	}
	
	if len(data) < overhead {
		return nil, errors.New("数据太短")
	}
	
	// 分离消息和签名
	message := data[:len(data)-hmacLen]
	signature := data[len(data)-hmacLen:]
	
	// 验证HMAC
	mac := hmac.New(sha256.New, signKey)
	mac.Write(message)
	expectedMAC := mac.Sum(nil)
	if !hmac.Equal(signature, expectedMAC) {
		return nil, errors.New("HMAC验证失败")
	}
	
	// 解析消息
	if message[0] != version {
		return nil, errors.New("不支持的版本")
	}
	
	timestampBytes := message[1 : 1+timestampLen]
	nonce := message[1+timestampLen : 1+timestampLen+nonceLen]
	ciphertext := message[1+timestampLen+nonceLen:]
	
	// 检查时间戳（可选，这里不验证过期）
	_ = timestampBytes
	
	// AES-128-CBC解密
	block, err := aes.NewCipher(encKey)
	if err != nil {
		return nil, err
	}
	
	if len(ciphertext)%aes.BlockSize != 0 {
		return nil, errors.New("密文长度不正确")
	}
	
	iv := make([]byte, aes.BlockSize)
	copy(iv, nonce)
	
	mode := cipher.NewCBCDecrypter(block, iv)
	plaintext := make([]byte, len(ciphertext))
	mode.CryptBlocks(plaintext, ciphertext)
	
	// 移除PKCS7填充
	padding := int(plaintext[len(plaintext)-1])
	if padding > aes.BlockSize || padding == 0 {
		return nil, errors.New("填充无效")
	}
	
	for i := len(plaintext) - padding; i < len(plaintext); i++ {
		if plaintext[i] != byte(padding) {
			return nil, errors.New("填充无效")
		}
	}
	
	return plaintext[:len(plaintext)-padding], nil
}

