package service

import (
	"context"
	"errors"

	"inventory/internal/repo"
)

var ErrNotFound = errors.New("item not found")

type InventoryService struct {
	items *repo.ItemRepo
}

func New(items *repo.ItemRepo) *InventoryService {
	return &InventoryService{items: items}
}

func (s *InventoryService) GetItem(ctx context.Context, sku string) (*repo.Item, error) {
	item, ok := s.items.Get(sku)
	if !ok {
		return nil, ErrNotFound
	}
	return item, nil
}

func (s *InventoryService) Adjust(ctx context.Context, sku string, delta int) error {
	item, ok := s.items.Get(sku)
	if !ok {
		return ErrNotFound
	}
	// BUG: stock can go negative when delta is a large negative number.
	item.Quantity += delta
	s.items.Put(item)
	return nil
}
