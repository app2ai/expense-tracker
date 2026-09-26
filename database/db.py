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


def get_user_by_id(user_id):
    """Return the user row for an id, or None (also None when user_id is None)."""
    if user_id is None:
        return None
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def get_recent_expenses(user_id, limit=10, start_date=None, end_date=None):
    """Return a user's newest expenses as plain dicts, newest first.

    Ordered by date then id (both descending) so same-day rows keep a stable order.
    A missing description comes back as an empty string. When start_date and
    end_date are both given (inclusive ISO 'YYYY-MM-DD' strings), only expenses
    in that range are returned; otherwise all of the user's expenses are eligible.
    """
    conn = get_db()
    try:
        sql = (
            "SELECT date, COALESCE(description, '') AS description, category, amount "
            "FROM expenses WHERE user_id = ?"
        )
        params = [user_id]
        if start_date and end_date:
            sql += " AND date BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        sql += " ORDER BY date DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]


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


def create_expense(user_id, amount, category, expense_date, description):
    """Insert an expense for a user and return the new id.

    expense_date is an ISO 'YYYY-MM-DD' string. A blank or whitespace-only
    description is stored as NULL. Callers validate the values first.
    """
    description = (description or "").strip() or None
    conn = get_db()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, expense_date, description),
            )
            return cursor.lastrowid
    finally:
        conn.close()


def get_expense_summary(user_id, start_date=None, end_date=None):
    """Return total_spent, transaction_count and top_category for a user.

    A user with no expenses (or none in the given range) gets 0.0, 0 and None.
    When start_date and end_date are both given (inclusive ISO 'YYYY-MM-DD'
    strings), only expenses in that range are counted.
    """
    conn = get_db()
    try:
        totals = _category_totals(conn, user_id, start_date, end_date)
    finally:
        conn.close()
    return {
        "total_spent": float(round(sum(total for _, total, _ in totals), 2)),
        "transaction_count": sum(count for _, _, count in totals),
        "top_category": totals[0][0] if totals else None,
    }


def _category_totals(conn, user_id, start_date=None, end_date=None):
    """Return (category, total, count) per category for a user, biggest spend first.

    Totals are rounded to 2 dp in SQL so genuine ties compare equal and fall back
    to alphabetical order. Empty list when the user has no expenses. When
    start_date and end_date are both given (inclusive ISO 'YYYY-MM-DD' strings),
    only expenses in that range are included; otherwise all expenses count.
    """
    sql = (
        "SELECT category, ROUND(SUM(amount), 2) AS total, COUNT(*) AS cnt "
        "FROM expenses WHERE user_id = ?"
    )
    params = [user_id]
    if start_date and end_date:
        sql += " AND date BETWEEN ? AND ?"
        params.extend([start_date, end_date])
    sql += " GROUP BY category ORDER BY total DESC, category ASC"
    rows = conn.execute(sql, params).fetchall()
    return [(row["category"], float(row["total"]), int(row["cnt"])) for row in rows]


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


def _allocate_percents(totals):
    """Return whole-number percents for amounts, summing to exactly 100.

    Largest-remainder method on integer cents, so there is no float drift.
    Remainder ties go to the earlier item. All zeros when the total is not positive.
    """
    cents = [round(total * 100) for total in totals]
    grand_total = sum(cents)
    if grand_total <= 0:
        return [0] * len(cents)
    percents = [(c * 100) // grand_total for c in cents]
    remainders = [(c * 100) % grand_total for c in cents]
    leftover = 100 - sum(percents)
    ranked = sorted(range(len(cents)), key=lambda i: (-remainders[i], i))
    for i in ranked[:leftover]:
        percents[i] += 1
    return percents


def get_category_breakdown(user_id, start_date=None, end_date=None):
    """Return a user's spend per category as name, amount and whole-number percent.

    Biggest spend first (ties alphabetical); percents sum to exactly 100.
    Empty list when the user has no expenses (or none in the given range). When
    start_date and end_date are both given (inclusive ISO 'YYYY-MM-DD' strings),
    only expenses in that range are included.
    """
    conn = get_db()
    try:
        totals = _category_totals(conn, user_id, start_date, end_date)
    finally:
        conn.close()
    percents = _allocate_percents([total for _, total, _ in totals])
    return [
        {"name": name, "amount": total, "percent": percent}
        for (name, total, _), percent in zip(totals, percents)
    ]
