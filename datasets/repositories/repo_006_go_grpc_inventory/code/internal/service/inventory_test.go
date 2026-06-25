package service

import (
	"context"
	"testing"

	"inventory/internal/repo"
)

func TestGetItemNotFound(t *testing.T) {
	svc := New(repo.NewItemRepo())
	if _, err := svc.GetItem(context.Background(), "missing"); err != ErrNotFound {
		t.Fatalf("expected ErrNotFound, got %v", err)
	}
}
