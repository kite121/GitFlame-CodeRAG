package store

import "strings"

const alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"

// Encode turns an integer id into a short base36 code.
func Encode(id int) string {
	if id == 0 {
		return "a"
	}
	var sb strings.Builder
	for id > 0 {
		sb.WriteByte(alphabet[id%len(alphabet)])
		id /= len(alphabet)
	}
	return sb.String()
}
