package main

import (
	"encoding/json"
	"fmt"

	authclient "github.com/Paper-Dragon/py-auth/client/go"
)

func main() {
	facts := authclient.CollectDeviceFacts()
	info := authclient.BuildDeviceInfo(facts, nil)
	b, _ := json.MarshalIndent(info, "", "  ")
	fmt.Println(string(b))
}
