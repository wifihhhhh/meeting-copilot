from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_PATH
from database.models import Base, utc_now_text


def make_sqlite_url(db_path: Path = DATABASE_PATH) -> str:
    return f"sqlite:///{db_path.as_posix()}"


engine = create_engine(
    make_sqlite_url(),
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db(db_path: Path = DATABASE_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    migrate_existing_schema()


def migrate_existing_schema() -> None:
    with engine.begin() as conn:
        now = utc_now_text()
        conn.execute(
            text(
                """
                INSERT OR IGNORE INTO users(id, username, password_hash, display_name, created_at)
                VALUES (1, 'demo', 'disabled', '演示用户', :now)
                """
            ),
            {"now": now},
        )

        meeting_columns = _table_columns(conn, "meetings")
        if "user_id" not in meeting_columns:
            conn.execute(text("ALTER TABLE meetings ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_meetings_user_id ON meetings(user_id)"))

        qa_columns = _table_columns(conn, "qa_records")
        if qa_columns and "user_id" not in qa_columns:
            conn.execute(text("ALTER TABLE qa_records ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_qa_records_user_id ON qa_records(user_id)"))

        eval_columns = _table_columns(conn, "evaluation_results")
        if eval_columns and "user_id" not in eval_columns:
            conn.execute(text("ALTER TABLE evaluation_results ADD COLUMN user_id INTEGER"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_evaluation_results_user_id ON evaluation_results(user_id)"))


def _table_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


@contextmanager
def get_session() -> Iterator[Session]:
    init_db()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
