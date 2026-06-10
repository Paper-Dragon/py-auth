//go:build !windows

package authclient

import "os/exec"

// hiddenCommand 在非 Windows 平台等价于 exec.Command。
func hiddenCommand(name string, args ...string) *exec.Cmd {
	return exec.Command(name, args...)
}
