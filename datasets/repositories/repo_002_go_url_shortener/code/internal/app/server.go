package app

import (
	"net/http"

	"shortener/internal/store"
)

type Server struct {
	store *store.MemoryStore
	mux   *http.ServeMux
}

func NewServer(s *store.MemoryStore) *Server {
	srv := &Server{store: s, mux: http.NewServeMux()}
	srv.routes()
	return srv
}

func (s *Server) routes() {
	s.mux.HandleFunc("/shorten", s.handleShorten)
	s.mux.HandleFunc("/r/", s.handleRedirect)
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.mux.ServeHTTP(w, r)
}
