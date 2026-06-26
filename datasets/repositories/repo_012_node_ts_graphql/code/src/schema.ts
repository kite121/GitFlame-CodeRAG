export const typeDefs = `
  type Author { id: ID!, name: String! }
  type Book { id: ID!, title: String!, author: Author! }
  type Query {
    books: [Book!]!
    book(id: ID!): Book
  }
  type Mutation {
    addBook(title: String!, authorId: ID!): Book!
  }
`;
