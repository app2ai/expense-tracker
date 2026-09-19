import importlib
import sys
from pathlib import Path

import pytest

# pytest does not put the repo root on sys.path, so `import app` / `import database` need it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import db  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Flask app bound to a throwaway database.

    NEVER `import app` at the top of a test module: importing it runs init_db()/seed_db()
    against whatever database.db.DB_PATH is at that moment (the real expense_tracker.db).
    """
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()

    flask_app = importlib.import_module("app").app
    flask_app.config["TESTING"] = True
    yield flask_app


def count_users():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()
