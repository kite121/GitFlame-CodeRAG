export interface Book {
  id: string;
  title: string;
  authorId: string;
}

export class BookRepo {
  private books: Book[] = [];
  private seq = 1;

  all(): Book[] {
    return this.books;
  }

  byId(id: string): Book | undefined {
    return this.books.find((b) => b.id === id);
  }

  create(title: string, authorId: string): Book {
    const book = { id: String(this.seq++), title, authorId };
    this.books.push(book);
    return book;
  }
}
