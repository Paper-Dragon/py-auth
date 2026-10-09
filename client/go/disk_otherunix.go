//go:build unix && !linux && !darwin

package authclient

import (
	"fmt"
	"os"
)

// OpenBSD and other non-Linux/Darwin Unix: Statfs_t field names differ,
// and disk fingerprinting is only implemented for linux/darwin.

func rootDiskTotalBytes() (uint64, error) {
	return 0, os.ErrNotExist
}

func rootDiskID() string {
	return "/"
}

func physicalMemoryBytes() (uint64, error) {
	return 0, os.ErrNotExist
}

func getDiskInfo() (map[string]float64, error) {
	return nil, fmt.Errorf("disk info not available")
}

func listDiskVolumes() (map[string]DeviceDiskModelGroup, error) {
	return nil, fmt.Errorf("disk volumes not available")
}
