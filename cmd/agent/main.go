package main

import (
	"bufio"
	"crypto/tls"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/Kukutx/Viper/internal/common"
	"github.com/Kukutx/Viper/internal/protocol"
)

const maxReadBytes = 1 << 20

func main() {
	server := flag.String("server", "localhost:8443", "Viper server address")
	insecure := flag.Bool("insecure", false, "allow unverified TLS certificate (development only)")
	name := flag.String("name", "", "device display name")
	flag.Parse()

	hostname, _ := os.Hostname()
	if *name == "" {
		*name = hostname
	}
	deviceID, err := common.RandomHex(16)
	if err != nil {
		log.Fatal(err)
	}
	pairCode, err := common.PairCode()
	if err != nil {
		log.Fatal(err)
	}

	raw, err := dialTLS(*server, *insecure)
	if err != nil {
		log.Fatal(err)
	}
	defer raw.Close()
	c := protocol.NewConn(raw)
	if err := c.Write(protocol.Message{Type: "hello", Role: "agent", DeviceID: deviceID, DeviceName: *name, Platform: runtime.GOOS + "/" + runtime.GOARCH, PairCode: pairCode}); err != nil {
		log.Fatal(err)
	}

	fmt.Printf("Viper Agent\n\nDevice: %s\nPlatform: %s/%s\nPair code: %s\nStatus: connected\n\n", *name, runtime.GOOS, runtime.GOARCH, pairCode)
	fmt.Println("Remote access is disabled until you approve a pairing request.")
	reader := bufio.NewReader(os.Stdin)

	for {
		msg, err := c.Read()
		if err != nil {
			log.Fatalf("connection closed: %v", err)
		}
		switch msg.Type {
		case "pair_prompt":
			requester := msg.DeviceName
			if requester == "" {
				requester = "remote controller"
			}
			fmt.Printf("\n%s requests remote assistance.\n", requester)
			fmt.Println("Capabilities: device info, directory listing, file read (max 1 MiB)")
			fmt.Print("Allow for up to 1 hour? [y/N]: ")
			line, _ := reader.ReadString('\n')
			answer := strings.TrimSpace(line)
			allow := strings.EqualFold(answer, "y") || strings.EqualFold(answer, "yes")
			_ = c.Write(protocol.Message{Type: "pair_decision", RequestID: msg.RequestID, Allow: allow, TTLSeconds: 3600})
			if allow {
				fmt.Println("Session approved. Close Viper Agent at any time to revoke access.")
			} else {
				fmt.Println("Request denied.")
			}
		case "info_request":
			host, _ := os.Hostname()
			content := fmt.Sprintf("hostname=%s\nos=%s\narch=%s\ngo=%s\n", host, runtime.GOOS, runtime.GOARCH, runtime.Version())
			_ = c.Write(protocol.Message{Type: "info_result", RequestID: msg.RequestID, Content: content})
		case "list_request":
			content, listErr := listDir(msg.Path)
			errText := ""
			if listErr != nil {
				errText = listErr.Error()
			}
			_ = c.Write(protocol.Message{Type: "list_result", RequestID: msg.RequestID, Content: content, Error: errText})
		case "read_request":
			content, readErr := readLimited(msg.Path)
			errText := ""
			if readErr != nil {
				errText = readErr.Error()
			}
			_ = c.Write(protocol.Message{Type: "read_result", RequestID: msg.RequestID, Content: content, Error: errText})
		}
	}
}

func dialTLS(address string, insecure bool) (net.Conn, error) {
	host := common.HostFromAddress(address)
	return tls.Dial("tcp", address, &tls.Config{MinVersion: tls.VersionTLS13, ServerName: host, InsecureSkipVerify: insecure}) //nolint:gosec -- explicit development-only CLI option
}

func listDir(path string) (string, error) {
	if strings.TrimSpace(path) == "" {
		path = "."
	}
	entries, err := os.ReadDir(path)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	for _, entry := range entries {
		kind := "file"
		if entry.IsDir() {
			kind = "dir"
		}
		fmt.Fprintf(&b, "%s\t%s\n", kind, filepath.Join(path, entry.Name()))
	}
	return b.String(), nil
}

func readLimited(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	r := io.LimitReader(f, maxReadBytes+1)
	b, err := io.ReadAll(r)
	if err != nil {
		return "", err
	}
	if len(b) > maxReadBytes {
		return "", fmt.Errorf("file exceeds %d byte read limit", maxReadBytes)
	}
	return string(b), nil
}
