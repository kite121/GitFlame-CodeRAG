<template>
  <ul class="note-list">
    <NoteItem v-for="note in sortedNotes" :key="note.id" :note="note" />
  </ul>
</template>

<script>
import { computed } from "vue";
import { state } from "../store/notes";
import NoteItem from "./NoteItem.vue";

export default {
  components: { NoteItem },
  setup() {
    // BUG: pinned notes are not floated to the top as designed.
    const sortedNotes = computed(() => state.notes);
    return { sortedNotes };
  },
};
</script>
