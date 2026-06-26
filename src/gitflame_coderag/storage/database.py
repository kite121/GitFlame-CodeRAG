from pathlib import Path

from pgvector.psycopg import register_vector
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import Connection


def create_engine_from_url(database_url: str) -> Engine:
    engine = create_engine(database_url, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _register_pgvector(dbapi_connection, _connection_record) -> None:
        register_vector(dbapi_connection)

    return engine


def run_migrations(engine: Engine, migrations_dir: Path | None = None) -> None:
    """Apply SQL migration files in lexical order."""
    if migrations_dir is None:
        migrations_dir = Path(__file__).resolve().parents[3] / "migrations"

    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        msg = f"No migration files found in {migrations_dir}"
        raise FileNotFoundError(msg)

    raw_connection = engine.raw_connection()
    try:
        raw_connection.autocommit = True
        cursor = raw_connection.cursor()
        try:
            for migration_file in migration_files:
                cursor.execute(migration_file.read_text(encoding="utf-8"))
        finally:
            cursor.close()
    finally:
        raw_connection.close()


def ping_database(connection: Connection) -> bool:
    try:
        connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
