import { createSchema } from "../src/server";

test("books query starts empty", () => {
  const { resolvers } = createSchema();
  expect(resolvers.Query.books()).toEqual([]);
});
