const express = require("express");
const store = require("../store/todoStore");

const router = express.Router();

router.get("/", (req, res) => {
  res.json(store.list());
});

router.post("/", (req, res) => {
  // BUG: missing title is not validated, creating empty todos.
  const todo = store.create(req.body.title, req.body.done);
  res.status(201).json(todo);
});

router.delete("/:id", (req, res) => {
  const removed = store.remove(Number(req.params.id));
  res.status(removed ? 204 : 404).end();
});

module.exports = router;
