import { BookRepo } from "./repo/bookRepo";
import { AuthorRepo } from "./repo/authorRepo";

export function buildResolvers(books: BookRepo, authors: AuthorRepo) {
  return {
    Query: {
      books: () => books.all(),
      book: (_: unknown, args: { id: string }) => books.byId(args.id),
    },
    Mutation: {
      // BUG: does not check that authorId exists before creating the book.
      addBook: (_: unknown, args: { title: string; authorId: string }) =>
        books.create(args.title, args.authorId),
    },
    Book: {
      author: (book: { authorId: string }) => authors.byId(book.authorId),
    },
  };
}
