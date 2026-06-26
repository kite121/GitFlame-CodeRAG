import { reactive } from "vue";

export const state = reactive({
  notes: [],
  nextId: 1,
});

export function addNote(title, body) {
  const note = { id: state.nextId++, title, body, pinned: false };
  state.notes.push(note);
  return note;
}

export function removeNote(id) {
  const index = state.notes.findIndex((n) => n.id === id);
  if (index >= 0) state.notes.splice(index, 1);
}

export function togglePin(id) {
  const note = state.notes.find((n) => n.id === id);
  if (note) note.pinned = !note.pinned;
}
