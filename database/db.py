import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now'))
)
"""

CREATE_EXPENSES_TABLE = """
CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      REAL NOT NULL,
    category    TEXT NOT NULL,
    date        TEXT NOT NULL,
    description TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users (id)
)
"""

# (day of month, category, amount, description)
SEED_EXPENSES = (
    (1, "Bills", 1850.00, "Electricity bill"),
    (3, "Food", 320.50, "Groceries"),
    (6, "Transport", 150.00, "Metro card recharge"),
    (9, "Health", 600.00, "Pharmacy"),
    (12, "Entertainment", 499.00, "Movie night"),
    (15, "Shopping", 1299.00, "Shoes"),
    (19, "Food", 245.75, "Dinner out"),
    (23, "Other", 200.00, "Miscellaneous"),
)


def get_db():
    """Return a SQLite connection with dict-like rows and foreign keys enforced."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not exist. Safe to call repeatedly."""
    conn = get_db()
    try:
        with conn:
            conn.execute(CREATE_USERS_TABLE)
            conn.execute(CREATE_EXPENSES_TABLE)
    finally:
        conn.close()


def get_user_by_email(email):
    """Return the user row for an email (case-insensitive), or None."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    finally:
        conn.close()


def create_user(name, email, password):
    """Insert a new user with a hashed password and return the new id.

    Raises sqlite3.IntegrityError if the email is already registered.
    """
    conn = get_db()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (
                    name.strip(),
                    email.strip().lower(),
                    generate_password_hash(password),
                ),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def seed_db():
    """Insert the demo user and sample expenses, unless users already exist."""
    conn = get_db()
    try:
        with conn:
            if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
                return

            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (
                    "Demo User",
                    "demo@spendly.com",
                    generate_password_hash("demo123"),
                ),
            )
            user_id = cursor.lastrowid

            today = date.today()
            rows = [
                (
                    user_id,
                    amount,
                    category,
                    date(today.year, today.month, day).isoformat(),
                    description,
                )
                for day, category, amount, description in SEED_EXPENSES
            ]
            conn.executemany(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                rows,
            )
    finally:
        conn.close()
