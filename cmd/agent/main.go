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
	rootFlag := flag.String("root", ".", "root directory exposed to approved sessions")
	flag.Parse()

	root, err := resolveRoot(*rootFlag)
	if err != nil {
		log.Fatalf("invalid -root: %v", err)
	}
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

	fmt.Printf("Viper Agent\n\nDevice: %s\nPlatform: %s/%s\nPair code: %s\nShared root: %s\nStatus: connected\n\n", *name, runtime.GOOS, runtime.GOARCH, pairCode, root)
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
			fmt.Println("Capabilities: device info, directory listing, file read (max 1 MiB within the configured root)")
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
			content, listErr := listDir(root, msg.Path)
			errText := ""
			if listErr != nil {
				errText = listErr.Error()
			}
			_ = c.Write(protocol.Message{Type: "list_result", RequestID: msg.RequestID, Content: content, Error: errText})
		case "read_request":
			content, readErr := readLimited(root, msg.Path)
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

func resolveRoot(path string) (string, error) {
	abs, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	resolved, err := filepath.EvalSymlinks(abs)
	if err != nil {
		return "", err
	}
	info, err := os.Stat(resolved)
	if err != nil {
		return "", err
	}
	if !info.IsDir() {
		return "", fmt.Errorf("%s is not a directory", path)
	}
	return resolved, nil
}

func resolveUnderRoot(root, requested string) (string, string, error) {
	requested = strings.TrimSpace(requested)
	if requested == "" {
		requested = "."
	}
	if filepath.IsAbs(requested) {
		return "", "", fmt.Errorf("absolute paths are not allowed")
	}
	clean := filepath.Clean(requested)
	candidate := filepath.Join(root, clean)
	resolved, err := filepath.EvalSymlinks(candidate)
	if err != nil {
		return "", "", err
	}
	rel, err := filepath.Rel(root, resolved)
	if err != nil {
		return "", "", err
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
		return "", "", fmt.Errorf("path escapes configured root")
	}
	return resolved, clean, nil
}

func listDir(root, path string) (string, error) {
	resolved, displayPath, err := resolveUnderRoot(root, path)
	if err != nil {
		return "", err
	}
	entries, err := os.ReadDir(resolved)
	if err != nil {
		return "", err
	}
	var b strings.Builder
	for _, entry := range entries {
		kind := "file"
		if entry.IsDir() {
			kind = "dir"
		}
		fmt.Fprintf(&b, "%s\t%s\n", kind, filepath.Join(displayPath, entry.Name()))
	}
	return b.String(), nil
}

func readLimited(root, path string) (string, error) {
	resolved, _, err := resolveUnderRoot(root, path)
	if err != nil {
		return "", err
	}
	f, err := os.Open(resolved)
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
