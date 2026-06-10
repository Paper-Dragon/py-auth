//go:build windows

package authclient

import (
	"os/exec"
	"syscall"
)

const createNoWindow = 0x08000000

// hiddenCommand 返回不会弹出控制台窗口的命令（GUI 程序中调用外部命令时必需）。
func hiddenCommand(name string, args ...string) *exec.Cmd {
	cmd := exec.Command(name, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		HideWindow:    true,
		CreationFlags: createNoWindow,
	}
	return cmd
}
