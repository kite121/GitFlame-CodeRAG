import { typeDefs } from "./schema";
import { buildResolvers } from "./resolvers";
import { BookRepo } from "./repo/bookRepo";
import { AuthorRepo } from "./repo/authorRepo";

export function createSchema() {
  const books = new BookRepo();
  const authors = new AuthorRepo();
  return { typeDefs, resolvers: buildResolvers(books, authors), books, authors };
}
