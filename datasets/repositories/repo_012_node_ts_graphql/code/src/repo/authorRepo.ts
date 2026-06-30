export interface Author {
  id: string;
  name: string;
}

export class AuthorRepo {
  private authors = new Map<string, Author>();

  add(author: Author): void {
    this.authors.set(author.id, author);
  }

  byId(id: string): Author | undefined {
    return this.authors.get(id);
  }
}
