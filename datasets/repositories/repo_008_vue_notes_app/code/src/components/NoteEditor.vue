<template>
  <form @submit.prevent="save">
    <input v-model="title" placeholder="Title" />
    <textarea v-model="body" placeholder="Body"></textarea>
    <button type="submit">Save</button>
  </form>
</template>

<script>
import { ref } from "vue";
import { addNote } from "../store/notes";

export default {
  setup() {
    const title = ref("");
    const body = ref("");
    function save() {
      // BUG: allows saving a note with an empty title.
      addNote(title.value, body.value);
      title.value = "";
      body.value = "";
    }
    return { title, body, save };
  },
};
</script>
