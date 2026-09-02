package protocol

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"sync"
)

const (
	Version         = 1
	MaxMessageBytes = 8 << 20
)

type Message struct {
	Version      int      `json:"version,omitempty"`
	Type         string   `json:"type"`
	Role         string   `json:"role,omitempty"`
	RequestID    string   `json:"request_id,omitempty"`
	DeviceID     string   `json:"device_id,omitempty"`
	DeviceName   string   `json:"device_name,omitempty"`
	Platform     string   `json:"platform,omitempty"`
	PairCode     string   `json:"pair_code,omitempty"`
	Allow        bool     `json:"allow,omitempty"`
	TTLSeconds   int      `json:"ttl_seconds,omitempty"`
	SessionToken string   `json:"session_token,omitempty"`
	ExpiresAt    string   `json:"expires_at,omitempty"`
	Capabilities []string `json:"capabilities,omitempty"`
	Path         string   `json:"path,omitempty"`
	Content      string   `json:"content,omitempty"`
	Error        string   `json:"error,omitempty"`
}

type Conn struct {
	r  *bufio.Reader
	w  io.Writer
	mu sync.Mutex
}

func NewConn(rw io.ReadWriter) *Conn {
	return &Conn{r: bufio.NewReader(rw), w: rw}
}

func (c *Conn) Read() (Message, error) {
	var wire bytes.Buffer
	for {
		fragment, err := c.r.ReadSlice('\n')
		if wire.Len()+len(fragment) > MaxMessageBytes {
			return Message{}, fmt.Errorf("protocol message exceeds %d bytes", MaxMessageBytes)
		}
		_, _ = wire.Write(fragment)
		if err == nil {
			break
		}
		if err == bufio.ErrBufferFull {
			continue
		}
		return Message{}, err
	}

	var msg Message
	if err := json.Unmarshal(wire.Bytes(), &msg); err != nil {
		return Message{}, err
	}
	if msg.Version != Version {
		return Message{}, fmt.Errorf("unsupported protocol version %d", msg.Version)
	}
	if msg.Type == "" {
		return Message{}, fmt.Errorf("protocol message type is required")
	}
	return msg, nil
}

func (c *Conn) Write(msg Message) error {
	if msg.Version == 0 {
		msg.Version = Version
	}
	data, err := json.Marshal(msg)
	if err != nil {
		return err
	}
	data = append(data, '\n')
	if len(data) > MaxMessageBytes {
		return fmt.Errorf("protocol message exceeds %d bytes", MaxMessageBytes)
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	_, err = c.w.Write(data)
	return err
}
