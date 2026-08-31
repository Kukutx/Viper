package main

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"flag"
	"fmt"
	"log"
	"math/big"
	"net"
	"sync"
	"time"

	"github.com/Kukutx/Viper/internal/common"
	"github.com/Kukutx/Viper/internal/protocol"
)

type peer struct {
	conn *protocol.Conn
	role string
	name string
}

type session struct {
	agent      *peer
	controller *peer
	expires    time.Time
}

type hub struct {
	mu       sync.Mutex
	agents   map[string]*peer
	pending  map[string]*peer
	requests map[string]*peer
	sessions map[string]session
}

func newHub() *hub {
	return &hub{agents: make(map[string]*peer), pending: make(map[string]*peer), requests: make(map[string]*peer), sessions: make(map[string]session)}
}

func main() {
	listen := flag.String("listen", ":8443", "TLS listen address")
	certFile := flag.String("cert", "", "TLS certificate PEM")
	keyFile := flag.String("key", "", "TLS private key PEM")
	flag.Parse()

	cert, generated, err := loadOrCreateCert(*certFile, *keyFile)
	if err != nil {
		log.Fatal(err)
	}
	ln, err := tls.Listen("tcp", *listen, &tls.Config{Certificates: []tls.Certificate{cert}, MinVersion: tls.VersionTLS13})
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("Viper server listening on %s", *listen)
	if generated {
		log.Printf("development self-signed TLS certificate in use; clients must explicitly use -insecure")
	}

	h := newHub()
	for {
		c, err := ln.Accept()
		if err != nil {
			log.Printf("accept: %v", err)
			continue
		}
		go h.handle(c)
	}
}

func (h *hub) handle(raw net.Conn) {
	defer raw.Close()
	pc := protocol.NewConn(raw)
	hello, err := pc.Read()
	if err != nil || hello.Type != "hello" || hello.Version != protocol.Version {
		return
	}
	p := &peer{conn: pc, role: hello.Role, name: hello.DeviceName}
	if hello.Role == "agent" {
		if hello.PairCode == "" {
			return
		}
		h.mu.Lock()
		h.agents[hello.PairCode] = p
		h.mu.Unlock()
		log.Printf("agent online name=%q platform=%s pair=%s", hello.DeviceName, hello.Platform, hello.PairCode)
	} else if hello.Role != "controller" {
		return
	}
	defer h.removePeer(p)

	for {
		msg, err := pc.Read()
		if err != nil {
			return
		}
		h.route(p, msg)
	}
}

func (h *hub) route(from *peer, msg protocol.Message) {
	switch msg.Type {
	case "pair_request":
		if from.role != "controller" {
			return
		}
		h.mu.Lock()
		agent := h.agents[msg.PairCode]
		if agent != nil {
			h.pending[msg.RequestID] = from
		}
		h.mu.Unlock()
		if agent == nil {
			_ = from.conn.Write(protocol.Message{Type: "pair_result", RequestID: msg.RequestID, Error: "pair code not found"})
			return
		}
		_ = agent.conn.Write(protocol.Message{Type: "pair_prompt", RequestID: msg.RequestID, DeviceName: from.name})

	case "pair_decision":
		if from.role != "agent" {
			return
		}
		h.mu.Lock()
		controller := h.pending[msg.RequestID]
		delete(h.pending, msg.RequestID)
		h.mu.Unlock()
		if controller == nil {
			return
		}
		if !msg.Allow {
			_ = controller.conn.Write(protocol.Message{Type: "pair_result", RequestID: msg.RequestID, Error: "remote user denied the request"})
			return
		}
		ttl := msg.TTLSeconds
		if ttl <= 0 || ttl > 3600 {
			ttl = 3600
		}
		token, err := common.RandomHex(32)
		if err != nil {
			_ = controller.conn.Write(protocol.Message{Type: "pair_result", RequestID: msg.RequestID, Error: "could not create session"})
			return
		}
		exp := time.Now().Add(time.Duration(ttl) * time.Second)
		h.mu.Lock()
		h.sessions[token] = session{agent: from, controller: controller, expires: exp}
		h.mu.Unlock()
		_ = controller.conn.Write(protocol.Message{Type: "pair_result", RequestID: msg.RequestID, SessionToken: token, ExpiresAt: exp.UTC().Format(time.RFC3339), Capabilities: []string{"device.info", "file.list", "file.read"}})

	case "info_request", "list_request", "read_request":
		if from.role != "controller" {
			return
		}
		s, ok := h.authorized(from, msg.SessionToken)
		if !ok {
			_ = from.conn.Write(protocol.Message{Type: resultType(msg.Type), RequestID: msg.RequestID, Error: "invalid or expired session"})
			return
		}
		h.mu.Lock()
		h.requests[msg.RequestID] = from
		h.mu.Unlock()
		_ = s.agent.conn.Write(msg)

	case "info_result", "list_result", "read_result":
		if from.role != "agent" {
			return
		}
		h.mu.Lock()
		controller := h.requests[msg.RequestID]
		delete(h.requests, msg.RequestID)
		h.mu.Unlock()
		if controller != nil {
			_ = controller.conn.Write(msg)
		}
	}
}

func (h *hub) authorized(controller *peer, token string) (session, bool) {
	h.mu.Lock()
	defer h.mu.Unlock()
	s, ok := h.sessions[token]
	if !ok || s.controller != controller || time.Now().After(s.expires) {
		if ok {
			delete(h.sessions, token)
		}
		return session{}, false
	}
	return s, true
}

func (h *hub) removePeer(p *peer) {
	h.mu.Lock()
	defer h.mu.Unlock()
	for code, a := range h.agents {
		if a == p {
			delete(h.agents, code)
		}
	}
	for token, s := range h.sessions {
		if s.agent == p || s.controller == p {
			delete(h.sessions, token)
		}
	}
	for id, c := range h.pending {
		if c == p {
			delete(h.pending, id)
		}
	}
	for id, c := range h.requests {
		if c == p {
			delete(h.requests, id)
		}
	}
}

func resultType(t string) string {
	switch t {
	case "info_request":
		return "info_result"
	case "list_request":
		return "list_result"
	case "read_request":
		return "read_result"
	default:
		return "error"
	}
}

func loadOrCreateCert(certFile, keyFile string) (tls.Certificate, bool, error) {
	if certFile != "" || keyFile != "" {
		if certFile == "" || keyFile == "" {
			return tls.Certificate{}, false, fmt.Errorf("-cert and -key must be supplied together")
		}
		cert, err := tls.LoadX509KeyPair(certFile, keyFile)
		return cert, false, err
	}
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return tls.Certificate{}, false, err
	}
	serialLimit := new(big.Int).Lsh(big.NewInt(1), 128)
	serial, err := rand.Int(rand.Reader, serialLimit)
	if err != nil {
		return tls.Certificate{}, false, err
	}
	tmpl := x509.Certificate{SerialNumber: serial, Subject: pkix.Name{CommonName: "Viper Development Server"}, NotBefore: time.Now().Add(-time.Minute), NotAfter: time.Now().Add(24 * time.Hour), KeyUsage: x509.KeyUsageDigitalSignature | x509.KeyUsageKeyEncipherment, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}, DNSNames: []string{"localhost"}}
	der, err := x509.CreateCertificate(rand.Reader, &tmpl, &tmpl, &key.PublicKey, key)
	if err != nil {
		return tls.Certificate{}, false, err
	}
	certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key)})
	cert, err := tls.X509KeyPair(certPEM, keyPEM)
	return cert, true, err
}
