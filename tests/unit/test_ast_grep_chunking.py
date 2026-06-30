import pytest

from gitflame_coderag.chunking import ast_grep
from gitflame_coderag.chunking.ast_grep import chunk_file_with_ast_grep, split_large_ast_chunk
from gitflame_coderag.chunking.datamodels import AstMatch
from gitflame_coderag.chunking.pipeline import build_chunks
from gitflame_coderag.schemas import AIConfig, ChunkingConfig, CodeChunk, FileMetadata, RepositoryFile


def make_file(path: str, language: str, content: str) -> RepositoryFile:
    return RepositoryFile(
        metadata=FileMetadata(
            id=f"repo:rev:{path}",
            repository_id="repo",
            revision="rev",
            path=path,
            extension=f".{path.rsplit('.', maxsplit=1)[-1]}",
            language=language,
            size_bytes=len(content.encode("utf-8")),
            line_count=len(content.splitlines()),
            content_hash="hash",
        ),
        raw_content=content,
    )


def test_split_large_ast_chunk_keeps_parent_chunk_metadata() -> None:
    content = "\n".join(f"line {number}" for number in range(1, 8))
    chunk = CodeChunk(
        id="chunk_ast_parent",
        repository_id="repo",
        file_id="file",
        path="sample.py",
        language="python",
        chunk_type="ast",
        node_type="class_definition",
        symbol_name="HugeService",
        parent_symbol=None,
        start_line=10,
        end_line=16,
        content=content,
        content_hash="hash",
        token_count=7,
    )
    config = ChunkingConfig(max_chunk_lines=4, overlap_lines=1)

    chunks = split_large_ast_chunk(chunk, config)

    assert [part.parent_chunk_id for part in chunks] == [
        "chunk_ast_parent",
        "chunk_ast_parent",
    ]
    assert [part.split_index for part in chunks] == [1, 2]
    assert [part.split_count for part in chunks] == [2, 2]
    assert [(part.start_line, part.end_line) for part in chunks] == [(10, 13), (13, 16)]


def test_python_ast_chunking_splits_toy_service(monkeypatch) -> None:
    content = "\n".join(
        [
            "class UserService:",
            "    def create_user(self, data):",
            "        return data",
            "",
            "def validate_email(email):",
            "    return '@' in email",
        ]
    )
    file = make_file("services/user_service.py", "python", content)

    def fake_scan(content: str, language: str, rules: list[str]) -> list[AstMatch]:
        del content, language, rules
        return [
            AstMatch(
                node=None,
                node_type="class_definition",
                symbol_name="UserService",
                parent_symbol=None,
                start_line=1,
                end_line=3,
                content="\n".join(file.raw_content.splitlines()[0:3]),
            ),
            AstMatch(
                node=None,
                node_type="function_definition",
                symbol_name="create_user",
                parent_symbol="UserService",
                start_line=2,
                end_line=3,
                content="\n".join(file.raw_content.splitlines()[1:3]),
            ),
            AstMatch(
                node=None,
                node_type="function_definition",
                symbol_name="validate_email",
                parent_symbol=None,
                start_line=5,
                end_line=6,
                content="\n".join(file.raw_content.splitlines()[4:6]),
            ),
        ]

    monkeypatch.setattr(ast_grep, "run_ast_grep_scan", fake_scan)

    chunks = chunk_file_with_ast_grep(file, ChunkingConfig(max_chunk_lines=20))

    assert [
        (chunk.node_type, chunk.symbol_name, chunk.parent_symbol, chunk.start_line, chunk.end_line)
        for chunk in chunks
    ] == [
        ("class_definition", "UserService", None, 1, 3),
        ("function_definition", "create_user", "UserService", 2, 3),
        ("function_definition", "validate_email", None, 5, 6),
    ]


def test_cpp_ast_chunking_splits_toy_service(monkeypatch) -> None:
    content = "\n".join(
        [
            "#include <string>",
            "",
            "class AuthService {",
            "public:",
            "    bool login(std::string email) {",
            "        return !email.empty();",
            "    }",
            "};",
            "",
            "int add(int a, int b) {",
            "    return a + b;",
            "}",
        ]
    )
    file = make_file("src/auth_service.cpp", "cpp", content)

    def fake_scan(content: str, language: str, rules: list[str]) -> list[AstMatch]:
        del content, language, rules
        return [
            AstMatch(
                node=None,
                node_type="class_specifier",
                symbol_name="AuthService",
                parent_symbol=None,
                start_line=3,
                end_line=8,
                content="\n".join(file.raw_content.splitlines()[2:8]),
            ),
            AstMatch(
                node=None,
                node_type="function_definition",
                symbol_name="login",
                parent_symbol="AuthService",
                start_line=5,
                end_line=7,
                content="\n".join(file.raw_content.splitlines()[4:7]),
            ),
            AstMatch(
                node=None,
                node_type="function_definition",
                symbol_name="add",
                parent_symbol=None,
                start_line=10,
                end_line=12,
                content="\n".join(file.raw_content.splitlines()[9:12]),
            ),
        ]

    monkeypatch.setattr(ast_grep, "run_ast_grep_scan", fake_scan)

    chunks = chunk_file_with_ast_grep(file, ChunkingConfig(max_chunk_lines=20))

    assert [
        (chunk.node_type, chunk.symbol_name, chunk.parent_symbol, chunk.start_line, chunk.end_line)
        for chunk in chunks
    ] == [
        ("class_specifier", "AuthService", None, 3, 8),
        ("function_definition", "login", "AuthService", 5, 7),
        ("function_definition", "add", None, 10, 12),
    ]


def test_unsupported_language_uses_fallback_window() -> None:
    content = "\n".join(f"line {number}" for number in range(1, 6))
    file = make_file("notes/example.txt", "text", content)
    config = AIConfig.model_validate(
        {"chunking": {"strategy": "ast_aware", "max_chunk_lines": 3, "overlap_lines": 1}}
    )

    chunks = build_chunks([file], config)

    assert [chunk.chunk_type for chunk in chunks] == ["fixed_window", "fixed_window"]
    assert [(chunk.start_line, chunk.end_line) for chunk in chunks] == [(1, 3), (3, 5)]


@pytest.mark.parametrize(
    ("path", "language", "content", "expected"),
    [
        (
            "src/userService.js",
            "javascript",
            "\n".join(
                [
                    "class UserService {",
                    "  createUser(data) {",
                    "    return data;",
                    "  }",
                    "}",
                    "",
                    "function validateEmail(email) {",
                    "  return email.includes('@');",
                    "}",
                ]
            ),
            [
                ("class_declaration", "UserService", None, 1, 5),
                ("method_definition", "createUser", "UserService", 2, 4),
                ("function_declaration", "validateEmail", None, 7, 9),
            ],
        ),
        (
            "src/userService.ts",
            "typescript",
            "\n".join(
                [
                    "interface User {",
                    "  email: string;",
                    "}",
                    "",
                    "class UserService {",
                    "  createUser(data: User): User {",
                    "    return data;",
                    "  }",
                    "}",
                    "",
                    "function validateEmail(email: string): boolean {",
                    "  return email.includes('@');",
                    "}",
                ]
            ),
            [
                ("interface_declaration", "User", None, 1, 3),
                ("class_declaration", "UserService", None, 5, 9),
                ("method_definition", "createUser", "UserService", 6, 8),
                ("function_declaration", "validateEmail", None, 11, 13),
            ],
        ),
        (
            "src/UserCard.tsx",
            "tsx",
            "\n".join(
                [
                    "type User = { name: string };",
                    "",
                    "export function UserCard(props: { user: User }) {",
                    "  return <div>{props.user.name}</div>;",
                    "}",
                ]
            ),
            [
                ("type_alias_declaration", "User", None, 1, 1),
                ("function_declaration", "UserCard", None, 3, 5),
            ],
        ),
        (
            "src/UserService.java",
            "java",
            "\n".join(
                [
                    "class UserService {",
                    "    public User createUser(User data) {",
                    "        return data;",
                    "    }",
                    "}",
                    "",
                    "interface Validator {",
                    "    boolean validate(String email);",
                    "}",
                ]
            ),
            [
                ("class_declaration", "UserService", None, 1, 5),
                ("method_declaration", "createUser", "UserService", 2, 4),
                ("interface_declaration", "Validator", None, 7, 9),
                ("method_declaration", "validate", "Validator", 8, 8),
            ],
        ),
        (
            "src/user_service.go",
            "go",
            "\n".join(
                [
                    "package main",
                    "",
                    "type UserService struct{}",
                    "",
                    "func (s UserService) CreateUser(data string) string {",
                    "    return data",
                    "}",
                    "",
                    "func ValidateEmail(email string) bool {",
                    "    return true",
                    "}",
                ]
            ),
            [
                ("type_declaration", "UserService", None, 3, 3),
                ("method_declaration", "CreateUser", None, 5, 7),
                ("function_declaration", "ValidateEmail", None, 9, 11),
            ],
        ),
        (
            "src/user_service.rs",
            "rust",
            "\n".join(
                [
                    "struct UserService;",
                    "",
                    "impl UserService {",
                    "    fn create_user(&self, data: String) -> String {",
                    "        data",
                    "    }",
                    "}",
                    "",
                    "fn validate_email(email: &str) -> bool {",
                    "    email.contains('@')",
                    "}",
                ]
            ),
            [
                ("struct_item", "UserService", None, 1, 1),
                ("impl_item", "create_user", None, 3, 7),
                ("function_item", "create_user", "create_user", 4, 6),
                ("function_item", "validate_email", None, 9, 11),
            ],
        ),
    ],
)
def test_real_ast_grep_chunking_for_supported_languages(
    path: str,
    language: str,
    content: str,
    expected: list[tuple[str, str | None, str | None, int, int]],
) -> None:
    pytest.importorskip("ast_grep_py")
    file = make_file(path, language, content)

    chunks = chunk_file_with_ast_grep(file, ChunkingConfig(max_chunk_lines=80))

    assert [
        (chunk.node_type, chunk.symbol_name, chunk.parent_symbol, chunk.start_line, chunk.end_line)
        for chunk in chunks
    ] == expected
