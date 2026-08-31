package main

import (
	"bufio"
	"crypto/tls"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"strings"
	"time"

	"github.com/Kukutx/Viper/internal/common"
	"github.com/Kukutx/Viper/internal/protocol"
)

func main() {
	server := flag.String("server", "localhost:8443", "Viper server address")
	insecure := flag.Bool("insecure", false, "allow unverified TLS certificate (development only)")
	name := flag.String("name", "", "controller display name")
	flag.Parse()

	if flag.NArg() != 2 || flag.Arg(0) != "connect" {
		fmt.Fprintf(os.Stderr, "usage: kuku [flags] connect <pair-code>\n")
		os.Exit(2)
	}
	pairCode := strings.ReplaceAll(flag.Arg(1), "-", "")
	hostname, _ := os.Hostname()
	if *name == "" {
		*name = hostname
	}

	raw, err := dialTLS(*server, *insecure)
	if err != nil {
		log.Fatal(err)
	}
	defer raw.Close()
	c := protocol.NewConn(raw)
	if err := c.Write(protocol.Message{Type: "hello", Role: "controller", DeviceName: *name}); err != nil {
		log.Fatal(err)
	}

	reqID, _ := common.RandomHex(8)
	if err := c.Write(protocol.Message{Type: "pair_request", RequestID: reqID, PairCode: pairCode}); err != nil {
		log.Fatal(err)
	}
	fmt.Println("Waiting for remote user approval...")
	msg, err := c.Read()
	if err != nil {
		log.Fatal(err)
	}
	if msg.Type != "pair_result" || msg.RequestID != reqID || msg.Error != "" {
		if msg.Error == "" {
			msg.Error = "unexpected pairing response"
		}
		log.Fatal(msg.Error)
	}
	token := msg.SessionToken
	fmt.Printf("Connected. Session expires %s\n", msg.ExpiresAt)
	fmt.Println("Commands: info | ls [path] | read <path> | quit")

	scanner := bufio.NewScanner(os.Stdin)
	for {
		fmt.Print("viper> ")
		if !scanner.Scan() {
			return
		}
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		if line == "quit" || line == "exit" {
			return
		}
		request, ok := buildRequest(line, token)
		if !ok {
			fmt.Println("invalid command")
			continue
		}
		if err := c.Write(request); err != nil {
			log.Fatal(err)
		}
		resp, err := c.Read()
		if err != nil {
			log.Fatal(err)
		}
		printResponse(resp)
	}
}

func buildRequest(line, token string) (protocol.Message, bool) {
	id, _ := common.RandomHex(8)
	if line == "info" {
		return protocol.Message{Type: "info_request", RequestID: id, SessionToken: token}, true
	}
	if line == "ls" {
		return protocol.Message{Type: "list_request", RequestID: id, SessionToken: token, Path: "."}, true
	}
	if strings.HasPrefix(line, "ls ") {
		path := strings.TrimSpace(strings.TrimPrefix(line, "ls "))
		if path == "" {
			return protocol.Message{}, false
		}
		return protocol.Message{Type: "list_request", RequestID: id, SessionToken: token, Path: path}, true
	}
	if strings.HasPrefix(line, "read ") {
		path := strings.TrimSpace(strings.TrimPrefix(line, "read "))
		if path == "" {
			return protocol.Message{}, false
		}
		return protocol.Message{Type: "read_request", RequestID: id, SessionToken: token, Path: path}, true
	}
	return protocol.Message{}, false
}

func printResponse(msg protocol.Message) {
	if msg.Error != "" {
		fmt.Printf("error: %s\n", msg.Error)
	}
	if msg.Content != "" {
		fmt.Print(msg.Content)
		if !strings.HasSuffix(msg.Content, "\n") {
			fmt.Println()
		}
	}
}

func dialTLS(address string, insecure bool) (net.Conn, error) {
	host := common.HostFromAddress(address)
	d := &net.Dialer{Timeout: 10 * time.Second}
	return tls.DialWithDialer(d, "tcp", address, &tls.Config{MinVersion: tls.VersionTLS13, ServerName: host, InsecureSkipVerify: insecure}) //nolint:gosec -- explicit development-only CLI option
}
