package authclient

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/google/uuid"
)

// DeviceFacts 设备硬件信息
type DeviceFacts struct {
	System    string
	Release   string
	Version   string
	Machine   string
	Processor string
	Hostname  string
	MAC       string
	IPAddress string
	CPUCount  int
	DiskID    string
}

// DeviceInfo 设备信息（发送给服务器）
type DeviceInfo struct {
	Hostname   string `json:"hostname,omitempty"`
	System     string `json:"system,omitempty"`
	Release    string `json:"release,omitempty"`
	Version    string `json:"version,omitempty"`
	Machine    string `json:"machine,omitempty"`
	Processor  string `json:"processor,omitempty"`
	MACAddress string `json:"mac_address,omitempty"`
	IPAddress  string `json:"ip_address,omitempty"`
	CPUCount   int    `json:"cpu_count,omitempty"`
	Username   string `json:"username,omitempty"`
}

// deviceIDStorePath 设备ID持久化路径
func deviceIDStorePath(serverURL, softwareName string) string {
	home, _ := os.UserHomeDir()
	base := filepath.Join(home, ".py_auth_device")
	os.MkdirAll(base, 0755)

	hash := sha256.Sum256([]byte(serverURL))
	serverHash := hex.EncodeToString(hash[:])[:12]

	var softHash string
	if softwareName != "" {
		hash2 := sha256.Sum256([]byte(softwareName))
		softHash = hex.EncodeToString(hash2[:])[:8]
	} else {
		softHash = "default"
	}

	return filepath.Join(base, fmt.Sprintf("device_%s_%s.txt", serverHash, softHash))
}

// LoadPersistedDeviceID 加载持久化的设备ID
func LoadPersistedDeviceID(serverURL, softwareName string) (string, error) {
	path := deviceIDStorePath(serverURL, softwareName)
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(data)), nil
}

// PersistDeviceID 持久化设备ID
func PersistDeviceID(serverURL, deviceID, softwareName string) error {
	path := deviceIDStorePath(serverURL, softwareName)
	return os.WriteFile(path, []byte(deviceID), 0644)
}

// GetMACAddress 获取主网卡MAC地址
func GetMACAddress() string {
	// 尝试使用net包获取
	interfaces, err := getNetworkInterfaces()
	if err == nil {
		for _, iface := range interfaces {
			if iface.MAC != "" && !strings.HasPrefix(iface.MAC, "00:00:00:00:00:00") {
				return iface.MAC
			}
		}
	}

	// 备用方案：使用系统命令
	if runtime.GOOS == "windows" {
		cmd := exec.Command("getmac", "/fo", "csv", "/nh")
		output, err := cmd.Output()
		if err == nil {
			lines := strings.Split(string(output), "\n")
			for _, line := range lines {
				parts := strings.Split(line, ",")
				if len(parts) >= 1 {
					mac := strings.TrimSpace(strings.Trim(parts[0], "\""))
					if mac != "" && !strings.HasPrefix(mac, "00-00-00-00-00-00") {
						mac = strings.ReplaceAll(mac, "-", ":")
						return mac
					}
				}
			}
		}
	} else if runtime.GOOS == "darwin" || runtime.GOOS == "linux" {
		cmd := exec.Command("ifconfig")
		output, err := cmd.Output()
		if err == nil {
			// 简单解析MAC地址
			lines := strings.Split(string(output), "\n")
			for _, line := range lines {
				if strings.Contains(line, "ether") || strings.Contains(line, "HWaddr") {
					parts := strings.Fields(line)
					for _, part := range parts {
						if len(part) == 17 && strings.Count(part, ":") == 5 {
							return part
						}
					}
				}
			}
		}
	}

	return ""
}

// CollectDeviceFacts 采集设备信息
func CollectDeviceFacts() DeviceFacts {
	facts := DeviceFacts{
		System:   runtime.GOOS,
		Machine:  runtime.GOARCH,
		Hostname: getHostname(),
	}

	// 获取系统信息
	facts.Release, facts.Version, facts.Processor = getSystemInfo()

	// 网络信息
	facts.MAC = GetMACAddress()
	facts.IPAddress = getIPAddress()

	// 硬件信息
	facts.CPUCount = runtime.NumCPU()

	// 磁盘ID（简化：仅使用基本路径）
	if runtime.GOOS == "windows" {
		facts.DiskID = "C:"
	} else {
		facts.DiskID = "/"
	}

	return facts
}

// BuildDeviceID 构建设备ID
func BuildDeviceID(serverURL string, providedDeviceID string, facts DeviceFacts, softwareName string) (string, error) {
	if providedDeviceID != "" {
		PersistDeviceID(serverURL, providedDeviceID, softwareName)
		return providedDeviceID, nil
	}

	// 尝试加载持久化的设备ID
	if persisted, err := LoadPersistedDeviceID(serverURL, softwareName); err == nil && persisted != "" {
		return persisted, nil
	}

	// 生成新的设备ID
	components := []string{
		facts.MAC,
		facts.DiskID,
		fmt.Sprintf("%d", facts.CPUCount),
		facts.System,
		facts.Machine,
		softwareName,
	}

	var filtered []string
	for _, c := range components {
		if c != "" && c != "0" {
			filtered = append(filtered, c)
		}
	}

	var deviceID string
	if len(filtered) > 0 {
		combined := strings.Join(filtered, "-")
		hash := sha256.Sum256([]byte(combined))
		deviceID = hex.EncodeToString(hash[:])[:32]
	} else {
		deviceID = uuid.New().String()
	}

	PersistDeviceID(serverURL, deviceID, softwareName)
	return deviceID, nil
}

// BuildDeviceInfo 构建设备信息
func BuildDeviceInfo(facts DeviceFacts, override *DeviceInfo) DeviceInfo {
	if override != nil {
		return *override
	}

	info := DeviceInfo{
		Hostname:  facts.Hostname,
		System:    facts.System,
		Release:   facts.Release,
		Version:   facts.Version,
		Machine:   facts.Machine,
		Processor: facts.Processor,
	}

	if facts.MAC != "" {
		info.MACAddress = facts.MAC
	}
	if facts.IPAddress != "" {
		info.IPAddress = facts.IPAddress
	}
	if facts.CPUCount > 0 {
		info.CPUCount = facts.CPUCount
	}

	// 获取用户名
	if u, err := user.Current(); err == nil {
		info.Username = u.Username
	}

	return info
}

// 辅助函数
func getHostname() string {
	hostname, err := os.Hostname()
	if err != nil {
		return "Unknown"
	}
	return hostname
}

func getSystemInfo() (release, version, processor string) {
	switch runtime.GOOS {
	case "windows":
		release = "Windows"
		// 尝试获取详细版本信息
		cmd := exec.Command("cmd", "/c", "ver")
		if output, err := cmd.Output(); err == nil {
			version = strings.TrimSpace(string(output))
		}
		processor = runtime.GOARCH
	case "darwin":
		release = "macOS"
		cmd := exec.Command("sw_vers", "-productVersion")
		if output, err := cmd.Output(); err == nil {
			release = "macOS " + strings.TrimSpace(string(output))
		}
		cmd = exec.Command("uname", "-m")
		if output, err := cmd.Output(); err == nil {
			processor = strings.TrimSpace(string(output))
		}
	case "linux":
		release = "Linux"
		// 尝试读取 /etc/os-release
		if data, err := os.ReadFile("/etc/os-release"); err == nil {
			lines := strings.Split(string(data), "\n")
			for _, line := range lines {
				if strings.HasPrefix(line, "PRETTY_NAME=") {
					release = strings.Trim(strings.TrimPrefix(line, "PRETTY_NAME="), "\"")
					break
				}
			}
		}
		cmd := exec.Command("uname", "-m")
		if output, err := cmd.Output(); err == nil {
			processor = strings.TrimSpace(string(output))
		}
	default:
		release = runtime.GOOS
		processor = runtime.GOARCH
	}
	return
}

func getIPAddress() string {
	interfaces, err := getNetworkInterfaces()
	if err == nil {
		for _, iface := range interfaces {
			if iface.IP != "" && !strings.HasPrefix(iface.IP, "127.") && !strings.HasPrefix(iface.IP, "169.254.") {
				return iface.IP
			}
		}
	}
	return ""
}
