package authclient

import (
	"crypto/sha256"
	"encoding/base64"
	"errors"

	"github.com/fernet/fernet-go"
)

// EncryptData 加密数据（兼容Python Fernet）
func EncryptData(data []byte, clientSecret string) (string, error) {
	if clientSecret == "" {
		return "", errors.New("client_secret不能为空")
	}

	// 使用CLIENT_SECRET的SHA256哈希作为密钥（与Python兼容）
	hash := sha256.Sum256([]byte(clientSecret))
	keyBytes := base64.URLEncoding.EncodeToString(hash[:32])

	// 使用fernet库加密
	key, err := fernet.DecodeKey(keyBytes)
	if err != nil {
		return "", err
	}

	token, err := fernet.EncryptAndSign(data, key)
	if err != nil {
		return "", err
	}
	// Fernet token本身就是URL-safe base64，直接转为字符串（与Python兼容）
	return string(token), nil
}

// DecryptData 解密数据（兼容Python Fernet）
func DecryptData(encryptedData string, clientSecret string) ([]byte, error) {
	if clientSecret == "" {
		return nil, errors.New("client_secret不能为空")
	}

	// 使用CLIENT_SECRET的SHA256哈希作为密钥
	hash := sha256.Sum256([]byte(clientSecret))
	keyBytes := base64.URLEncoding.EncodeToString(hash[:32])

	// 使用fernet库解密
	key, err := fernet.DecodeKey(keyBytes)
	if err != nil {
		return nil, err
	}

	// Fernet token本身就是URL-safe base64，直接转为bytes（与Python兼容）
	result := fernet.VerifyAndDecrypt([]byte(encryptedData), 0, []*fernet.Key{key})
	return result, nil
}
