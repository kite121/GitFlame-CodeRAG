package service

import "time"

type AuditEntry struct {
	SKU   string
	Delta int
	At    time.Time
}

// Log is a placeholder audit sink; entries are dropped on the floor today.
func Log(entry AuditEntry) {
	_ = entry
}
