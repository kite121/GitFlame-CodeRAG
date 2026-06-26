package app

import (
	"encoding/json"
	"net/http"
	"strings"
)

type shortenRequest struct {
	URL string `json:"url"`
}

func (s *Server) handleShorten(w http.ResponseWriter, r *http.Request) {
	var req shortenRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	// BUG: empty URLs are accepted and produce a dangling short code.
	code := s.store.Save(req.URL)
	json.NewEncoder(w).Encode(map[string]string{"code": code})
}

func (s *Server) handleRedirect(w http.ResponseWriter, r *http.Request) {
	code := strings.TrimPrefix(r.URL.Path, "/r/")
	target, ok := s.store.Resolve(code)
	if !ok {
		http.NotFound(w, r)
		return
	}
	http.Redirect(w, r, target, http.StatusFound)
}
