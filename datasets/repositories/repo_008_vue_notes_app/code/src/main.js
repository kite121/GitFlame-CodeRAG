import { createApp } from "vue";
import NoteList from "./components/NoteList.vue";
import NoteEditor from "./components/NoteEditor.vue";

const app = createApp({
  components: { NoteList, NoteEditor },
  template: "<NoteEditor /><NoteList />",
});

app.mount("#app");
