package store

import (
	"fmt"
	"sync"
)

type MemoryStore struct {
	mu    sync.Mutex
	urls  map[string]string
	count int
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{urls: make(map[string]string)}
}

func (m *MemoryStore) Save(url string) string {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.count++
	code := fmt.Sprintf("c%d", m.count)
	m.urls[code] = url
	return code
}

func (m *MemoryStore) Resolve(code string) (string, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	url, ok := m.urls[code]
	return url, ok
}
