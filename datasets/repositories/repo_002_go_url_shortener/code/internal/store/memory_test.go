package store

import "testing"

func TestSaveAndResolve(t *testing.T) {
	m := NewMemoryStore()
	code := m.Save("https://example.com")
	got, ok := m.Resolve(code)
	if !ok || got != "https://example.com" {
		t.Fatalf("resolve failed: %q %v", got, ok)
	}
}
