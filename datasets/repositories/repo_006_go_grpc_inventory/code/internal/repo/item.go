package repo

import "sync"

type Item struct {
	SKU      string
	Name     string
	Quantity int
}

type ItemRepo struct {
	mu    sync.RWMutex
	items map[string]*Item
}

func NewItemRepo() *ItemRepo {
	return &ItemRepo{items: make(map[string]*Item)}
}

func (r *ItemRepo) Get(sku string) (*Item, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	item, ok := r.items[sku]
	return item, ok
}

func (r *ItemRepo) Put(item *Item) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.items[item.SKU] = item
}
