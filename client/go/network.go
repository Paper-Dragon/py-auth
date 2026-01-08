package authclient

import (
	"net"
)

// NetworkInterface 网络接口信息
type NetworkInterface struct {
	MAC string
	IP  string
}

// getNetworkInterfaces 获取网络接口信息
func getNetworkInterfaces() ([]NetworkInterface, error) {
	var result []NetworkInterface

	interfaces, err := net.Interfaces()
	if err != nil {
		return result, err
	}

	for _, iface := range interfaces {
		if iface.Flags&net.FlagUp == 0 {
			continue
		}
		if iface.Flags&net.FlagLoopback != 0 {
			continue
		}

		mac := iface.HardwareAddr.String()
		if mac == "" {
			continue
		}

		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}

		var ip string
		for _, addr := range addrs {
			ipNet, ok := addr.(*net.IPNet)
			if !ok {
				continue
			}
			ipv4 := ipNet.IP.To4()
			if ipv4 != nil {
				ip = ipv4.String()
				break
			}
		}

		result = append(result, NetworkInterface{
			MAC: mac,
			IP:  ip,
		})
	}

	return result, nil
}
