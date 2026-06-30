const express = require("express");
const todosRouter = require("./routes/todos");
const { errorHandler } = require("./middleware/errors");

function createApp() {
  const app = express();
  app.use(express.json());
  app.use("/todos", todosRouter);
  app.use(errorHandler);
  return app;
}

module.exports = { createApp };
