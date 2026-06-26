package main

import (
	"log"

	"inventory/internal/repo"
	"inventory/internal/server"
	"inventory/internal/service"
)

func main() {
	items := repo.NewItemRepo()
	svc := service.New(items)
	handler := server.NewHandler(svc)
	_ = handler
	log.Println("inventory service ready")
}
