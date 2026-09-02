package protocol

import (
	"bytes"
	"strings"
	"testing"
)

type rw struct{ *bytes.Buffer }

func TestRoundTrip(t *testing.T) {
	b := &rw{bytes.NewBuffer(nil)}
	c := NewConn(b)
	want := Message{Type: "read_request", RequestID: "r1", Path: "README.md"}
	if err := c.Write(want); err != nil {
		t.Fatal(err)
	}
	got, err := c.Read()
	if err != nil {
		t.Fatal(err)
	}
	if got.Version != Version || got.Type != want.Type || got.RequestID != want.RequestID || got.Path != want.Path {
		t.Fatalf("unexpected round trip: %#v", got)
	}
}

func TestReadRejectsOversizedMessage(t *testing.T) {
	payload := strings.Repeat("x", MaxMessageBytes+1) + "\n"
	c := NewConn(&rw{bytes.NewBufferString(payload)})
	if _, err := c.Read(); err == nil {
		t.Fatal("expected oversized message to be rejected")
	}
}

func TestReadRejectsMissingVersion(t *testing.T) {
	c := NewConn(&rw{bytes.NewBufferString("{\"type\":\"hello\"}\n")})
	if _, err := c.Read(); err == nil {
		t.Fatal("expected missing protocol version to be rejected")
	}
}
