function errorHandler(err, req, res, next) {
  // NOTE: leaks stack traces to clients in all environments.
  res.status(err.status || 500).json({ error: err.message, stack: err.stack });
}

module.exports = { errorHandler };
