package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestResolveUnderRootBlocksTraversal(t *testing.T) {
	base := t.TempDir()
	rootDir := filepath.Join(base, "root")
	if err := os.Mkdir(rootDir, 0o755); err != nil {
		t.Fatal(err)
	}
	outside := filepath.Join(base, "outside.txt")
	if err := os.WriteFile(outside, []byte("secret"), 0o600); err != nil {
		t.Fatal(err)
	}
	root, err := resolveRoot(rootDir)
	if err != nil {
		t.Fatal(err)
	}
	if _, _, err := resolveUnderRoot(root, "../outside.txt"); err == nil {
		t.Fatal("expected path traversal to be rejected")
	}
}

func TestReadLimitedWithinRoot(t *testing.T) {
	rootDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(rootDir, "hello.txt"), []byte("hello"), 0o600); err != nil {
		t.Fatal(err)
	}
	root, err := resolveRoot(rootDir)
	if err != nil {
		t.Fatal(err)
	}
	got, err := readLimited(root, "hello.txt")
	if err != nil {
		t.Fatal(err)
	}
	if got != "hello" {
		t.Fatalf("unexpected content %q", got)
	}
}
