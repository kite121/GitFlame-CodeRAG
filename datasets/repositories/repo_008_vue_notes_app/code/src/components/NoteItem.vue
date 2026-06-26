<template>
  <li :class="{ pinned: note.pinned }">
    <h3>{{ note.title }}</h3>
    <p>{{ note.body }}</p>
    <button @click="onPin">Pin</button>
    <button @click="onDelete">Delete</button>
  </li>
</template>

<script>
import { removeNote, togglePin } from "../store/notes";

export default {
  props: { note: { type: Object, required: true } },
  setup(props) {
    return {
      onPin: () => togglePin(props.note.id),
      onDelete: () => removeNote(props.note.id),
    };
  },
};
</script>
