# Dataset Layout

Sprint 1 ships **12 synthetic sample repositories** under
`datasets/repositories/<repository_id>/`:

```text
repo_001_fastapi_blog/
  repo.yml          # repository config (follows the project template)
  issues.jsonl      # 7 GitHub-like synthetic issues
  code/             # realistic source files
    ...
```

Each `repo.yml` follows the template documented in `context.md`
(`analysis.include` / `analysis.exclude` drive file filtering).

Each issue line in `issues.jsonl` contains `id`, `title`, `body`, `labels` and
`expected_files`. `expected_chunks` is intentionally deferred beyond Sprint 1.

All code is original/synthetic and license-safe to commit; issues are marked
`source: synthetic` in each `repo.yml`.

## Repositories

| id | name | languages |
|---|---|---|
| repo_001_fastapi_blog | fastapi-blog | python |
| repo_002_go_url_shortener | go-url-shortener | go |
| repo_003_express_todo_api | express-todo-api | javascript |
| repo_004_react_dashboard | react-metrics-dashboard | typescript |
| repo_005_flask_auth_service | flask-auth-service | python |
| repo_006_go_grpc_inventory | go-grpc-inventory | go |
| repo_007_django_shop | django-shop | python |
| repo_008_vue_notes_app | vue-notes-app | javascript/vue |
| repo_009_nestjs_payments | nestjs-payments | typescript |
| repo_010_rust_cli_tool | rust-cli-linecount | rust |
| repo_011_python_etl_pipeline | python-etl-pipeline | python |
| repo_012_node_ts_graphql | node-ts-graphql-books | typescript |

84 issues and 74 code files in total.

## Loading in code

```python
from pathlib import Path
from gitflame_coderag.config.loader import load_ai_config, parse_ai_config
from gitflame_coderag.ingestion import load_repository_files, filter_files_by_config, load_issues

repo = Path("datasets/repositories/repo_001_fastapi_blog")
config = parse_ai_config(load_ai_config(repo / "repo.yml"))
files = load_repository_files(repo / "code", "repo_001_fastapi_blog", "local")
files = filter_files_by_config(files, config)
issues = load_issues(repo / "issues.jsonl", "repo_001_fastapi_blog")
```
