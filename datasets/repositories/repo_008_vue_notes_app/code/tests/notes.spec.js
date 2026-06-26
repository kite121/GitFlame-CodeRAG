import { addNote, state } from "../src/store/notes";

test("addNote appends a note", () => {
  const before = state.notes.length;
  addNote("t", "b");
  expect(state.notes.length).toBe(before + 1);
});
