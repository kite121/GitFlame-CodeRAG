package server

import (
	"context"

	"inventory/internal/service"
)

type Handler struct {
	svc *service.InventoryService
}

func NewHandler(svc *service.InventoryService) *Handler {
	return &Handler{svc: svc}
}

func (h *Handler) GetItem(ctx context.Context, sku string) (map[string]any, error) {
	item, err := h.svc.GetItem(ctx, sku)
	if err != nil {
		return nil, err
	}
	return map[string]any{"sku": item.SKU, "qty": item.Quantity}, nil
}

func (h *Handler) AdjustStock(ctx context.Context, sku string, delta int) error {
	return h.svc.Adjust(ctx, sku, delta)
}
