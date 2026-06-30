const store = require("../src/store/todoStore");

test("create then list returns the todo", () => {
  const todo = store.create("buy milk");
  expect(store.list()).toContainEqual(todo);
});
