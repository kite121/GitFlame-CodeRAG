package main

import (
	"log"
	"net/http"

	"shortener/internal/app"
	"shortener/internal/store"
)

func main() {
	srv := app.NewServer(store.NewMemoryStore())
	log.Println("listening on :8080")
	if err := http.ListenAndServe(":8080", srv); err != nil {
		log.Fatal(err)
	}
}
