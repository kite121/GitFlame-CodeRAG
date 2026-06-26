let nextId = 1;
const todos = new Map();

function create(title, done = false) {
  const id = nextId++;
  const todo = { id, title, done };
  todos.set(id, todo);
  return todo;
}

function list() {
  return Array.from(todos.values());
}

function remove(id) {
  return todos.delete(id);
}

function toggle(id) {
  const todo = todos.get(id);
  if (!todo) return null;
  todo.done = !todo.done;
  return todo;
}

module.exports = { create, list, remove, toggle };
