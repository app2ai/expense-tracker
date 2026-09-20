"""Tests for the profile page's real data: summary stats, recent transactions
and category breakdown (Step 5)."""
from datetime import date
from pathlib import Path

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
APP_PATH = Path(__file__).resolve().parents[1] / "app.py"

DEMO_BREAKDOWN = [
    ("Bills", 1850.00, 36),
    ("Shopping", 1299.00, 25),
    ("Health", 600.00, 11),
    ("Food", 566.25, 11),
    ("Entertainment", 499.00, 10),
    ("Other", 200.00, 4),
    ("Transport", 150.00, 3),
]


def _add_expense(user_id, amount, category, date, description="x"):
    import database.db as db

    conn = db.get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, date, description),
            )
    finally:
        conn.close()


def _demo_id():
    import database.db as db

    return db.get_user_by_email(DEMO_EMAIL)["id"]


def _new_user(name="Fresh User", email="fresh@example.com", password="secret123"):
    import database.db as db

    return db.create_user(name, email, password)


def _seed_date(day):
    today = date.today()
    return date(today.year, today.month, day).isoformat()


def _login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


# ---------------------------------------------------------------- stats ---

def test_demo_user_summary(app):
    import database.db as db

    assert db.get_expense_summary(_demo_id()) == {
        "total_spent": 5164.25,
        "transaction_count": 8,
        "top_category": "Bills",
    }


def test_new_user_summary_is_empty(app):
    import database.db as db

    assert db.get_expense_summary(_new_user()) == {
        "total_spent": 0.0,
        "transaction_count": 0,
        "top_category": None,
    }


def test_summary_types(app):
    import database.db as db

    summary = db.get_expense_summary(_demo_id())
    assert isinstance(summary["total_spent"], float)
    assert isinstance(summary["transaction_count"], int)
    empty = db.get_expense_summary(_new_user())
    assert isinstance(empty["total_spent"], float)


def test_tie_break_is_alphabetical(app):
    import database.db as db

    user_id = _new_user()
    _add_expense(user_id, 100.0, "Transport", "2026-01-01")
    _add_expense(user_id, 100.0, "Food", "2026-01-02")
    _add_expense(user_id, 100.0, "Health", "2026-01-03")

    summary = db.get_expense_summary(user_id)
    assert summary["top_category"] == "Food"
    assert summary["transaction_count"] == 3
    assert summary["total_spent"] == 300.0


def test_top_category_is_by_total_not_count(app):
    import database.db as db

    user_id = _new_user()
    _add_expense(user_id, 10.0, "Food", "2026-01-01")
    _add_expense(user_id, 10.0, "Food", "2026-01-02")
    _add_expense(user_id, 10.0, "Food", "2026-01-03")
    _add_expense(user_id, 500.0, "Shopping", "2026-01-04")

    assert db.get_expense_summary(user_id)["top_category"] == "Shopping"


def test_float_sum_is_rounded(app):
    import database.db as db

    user_id = _new_user()
    for day in (1, 2, 3):
        _add_expense(user_id, 0.1, "Food", f"2026-01-0{day}")

    summary = db.get_expense_summary(user_id)
    assert summary["total_spent"] == 0.3
    assert summary["transaction_count"] == 3


def test_summary_only_counts_own_expenses(app):
    import database.db as db

    alice = _new_user(email="alice@example.com")
    bob = _new_user(email="bob@example.com")
    _add_expense(alice, 111.11, "Food", "2026-01-01")
    _add_expense(alice, 50.0, "Food", "2026-01-02")
    _add_expense(bob, 222.22, "Travel", "2026-01-03")

    assert db.get_expense_summary(alice) == {
        "total_spent": 161.11,
        "transaction_count": 2,
        "top_category": "Food",
    }
    assert db.get_expense_summary(bob) == {
        "total_spent": 222.22,
        "transaction_count": 1,
        "top_category": "Travel",
    }
    # Demo user is untouched by the new users' rows.
    assert db.get_expense_summary(_demo_id())["total_spent"] == 5164.25


def test_route_demo_profile_shows_total_and_top_badge(client):
    client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    response = client.get("/profile")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "₹5,164.25" in html
    assert "badge-bills" in html


def test_route_new_user_profile_shows_empty_stats(client):
    import database.db as db

    db.create_user("Fresh User", "fresh@example.com", "secret123")
    client.post("/login", data={"email": "fresh@example.com", "password": "secret123"})
    response = client.get("/profile")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "₹0.00" in html
    assert "—" in html
    assert "badge-none" not in html


# --------------------------------------------------- transactions ---

def test_demo_user_gets_all_eight_seeded_rows(app):
    import database.db as db

    rows = db.get_recent_expenses(_demo_id())
    assert len(rows) == len(db.SEED_EXPENSES) == 8


def test_rows_are_plain_dicts_with_expected_keys(app):
    import database.db as db

    rows = db.get_recent_expenses(_demo_id())
    for row in rows:
        assert type(row) is dict
        assert set(row) == {"date", "description", "category", "amount"}


def test_dates_are_non_increasing(app):
    import database.db as db

    dates = [row["date"] for row in db.get_recent_expenses(_demo_id())]
    assert dates == sorted(dates, reverse=True)


def test_first_row_is_latest_seeded_expense(app):
    import database.db as db

    day, category, amount, description = max(db.SEED_EXPENSES, key=lambda s: s[0])
    first = db.get_recent_expenses(_demo_id())[0]
    assert first == {
        "date": _seed_date(day),
        "description": description,
        "category": category,
        "amount": amount,
    }
    assert (first["description"], first["category"], first["amount"]) == (
        "Miscellaneous",
        "Other",
        200.0,
    )


def test_new_user_has_no_recent_expenses(app):
    import database.db as db

    assert db.get_recent_expenses(_new_user()) == []


def test_default_limit_is_ten(app):
    import database.db as db

    uid = _new_user()
    for i in range(12):
        _add_expense(uid, 10 + i, "Food", f"2025-01-{i + 1:02d}", f"item {i}")
    rows = db.get_recent_expenses(uid)
    assert len(rows) == 10
    # Newest ten: days 12 down to 3.
    assert rows[0]["date"] == "2025-01-12"
    assert rows[-1]["date"] == "2025-01-03"


def test_limit_parameter_is_honoured(app):
    import database.db as db

    uid = _new_user()
    for i in range(12):
        _add_expense(uid, 10 + i, "Food", f"2025-01-{i + 1:02d}")
    assert len(db.get_recent_expenses(uid, limit=3)) == 3
    assert len(db.get_recent_expenses(uid, limit=12)) == 12
    assert len(db.get_recent_expenses(uid, limit=50)) == 12


def test_same_date_rows_higher_id_first(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 1, "Food", "2025-03-05", "first inserted")
    _add_expense(uid, 2, "Food", "2025-03-05", "second inserted")
    _add_expense(uid, 3, "Food", "2025-03-05", "third inserted")
    descriptions = [row["description"] for row in db.get_recent_expenses(uid)]
    assert descriptions == ["third inserted", "second inserted", "first inserted"]


def test_null_description_becomes_empty_string(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 50, "Other", "2025-03-05", None)
    rows = db.get_recent_expenses(uid)
    assert rows[0]["description"] == ""


def test_amount_is_float(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 100, "Bills", "2025-03-05", "whole number")
    _add_expense(uid, 12.5, "Food", "2025-03-04", "fraction")
    rows = db.get_recent_expenses(uid)
    assert all(type(row["amount"]) is float for row in rows)
    assert [row["amount"] for row in rows] == [100.0, 12.5]


def test_users_are_isolated(app):
    import database.db as db

    alpha = _new_user("Alpha", "alpha@example.com")
    beta = _new_user("Beta", "beta@example.com")
    _add_expense(alpha, 111.11, "Food", "2025-04-01", "ALPHA-ONLY")
    _add_expense(beta, 222.22, "Bills", "2025-04-02", "BETA-ONLY")

    alpha_rows = db.get_recent_expenses(alpha)
    beta_rows = db.get_recent_expenses(beta)

    assert [r["description"] for r in alpha_rows] == ["ALPHA-ONLY"]
    assert [r["amount"] for r in alpha_rows] == [111.11]
    assert [r["description"] for r in beta_rows] == ["BETA-ONLY"]
    assert [r["amount"] for r in beta_rows] == [222.22]
    # The demo user's rows never leak into either new user's list.
    assert len(db.get_recent_expenses(_demo_id())) == 8


def test_route_demo_profile_lists_eight_rows_newest_first(client):
    _login(client)
    response = client.get("/profile")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count("tx-row") == 8
    assert html.index("Miscellaneous") < html.index("Electricity bill")


def test_route_new_user_sees_empty_transactions_state(client):
    _new_user(email="route-fresh@example.com", password="secret123")
    _login(client, "route-fresh@example.com", "secret123")
    response = client.get("/profile")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "No transactions yet." in html
    assert "tx-row" not in html


# ----------------------------------------------------- categories ---

def test_demo_breakdown_order_amounts_and_percents(app):
    import database.db as db

    breakdown = db.get_category_breakdown(_demo_id())
    assert len(breakdown) == 7
    assert [(b["name"], b["amount"], b["percent"]) for b in breakdown] == DEMO_BREAKDOWN


def test_demo_breakdown_percents_sum_to_100(app):
    import database.db as db

    breakdown = db.get_category_breakdown(_demo_id())
    assert sum(b["percent"] for b in breakdown) == 100
    assert all(isinstance(b["percent"], int) for b in breakdown)


def test_new_user_breakdown_is_empty(app):
    import database.db as db

    assert db.get_category_breakdown(_new_user()) == []


def test_single_category_is_100_percent(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 10.0, "Food", "2026-01-01")
    _add_expense(uid, 15.5, "Food", "2026-01-02")
    assert db.get_category_breakdown(uid) == [
        {"name": "Food", "amount": 25.5, "percent": 100}
    ]


def test_three_equal_categories_split_34_33_33(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 100.0, "Food", "2026-01-01")
    _add_expense(uid, 100.0, "Bills", "2026-01-02")
    _add_expense(uid, 100.0, "Health", "2026-01-03")
    breakdown = db.get_category_breakdown(uid)
    # Ties are alphabetical, and the extra point goes to the first in that order.
    assert [(b["name"], b["percent"]) for b in breakdown] == [
        ("Bills", 34),
        ("Food", 33),
        ("Health", 33),
    ]
    assert sum(b["percent"] for b in breakdown) == 100


def test_equal_totals_are_ordered_alphabetically(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 50.0, "Transport", "2026-01-01")
    _add_expense(uid, 50.0, "Entertainment", "2026-01-02")
    assert [b["name"] for b in db.get_category_breakdown(uid)] == [
        "Entertainment",
        "Transport",
    ]


def test_float_noise_does_not_break_ties(app):
    import database.db as db

    uid = _new_user()
    for _ in range(3):
        _add_expense(uid, 0.1, "Food", "2026-01-01")
    _add_expense(uid, 0.3, "Bills", "2026-01-02")
    breakdown = db.get_category_breakdown(uid)
    assert [b["name"] for b in breakdown] == ["Bills", "Food"]
    assert [b["percent"] for b in breakdown] == [50, 50]


def test_breakdown_is_isolated_per_user(app):
    import database.db as db

    alpha = _new_user(email="alpha@example.com")
    beta = _new_user(email="beta@example.com")
    _add_expense(alpha, 111.11, "Food", "2026-01-01")
    _add_expense(beta, 222.22, "Bills", "2026-01-01")
    assert db.get_category_breakdown(alpha) == [
        {"name": "Food", "amount": 111.11, "percent": 100}
    ]
    assert db.get_category_breakdown(beta) == [
        {"name": "Bills", "amount": 222.22, "percent": 100}
    ]
    assert len(db.get_category_breakdown(_demo_id())) == 7


def test_breakdown_for_unknown_user_is_empty(app):
    import database.db as db

    assert db.get_category_breakdown(9999) == []


def test_route_demo_profile_shows_breakdown_rows(app, client):
    _login(client, DEMO_EMAIL, DEMO_PASSWORD)
    response = client.get("/profile")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Spending by category" in html
    assert html.count("breakdown-row") == 7
    assert "breakdown-list" in html
    assert "No spending to show yet." not in html


def test_route_fresh_user_sees_breakdown_empty_state(app, client):
    _new_user()
    _login(client, "fresh@example.com", "secret123")
    response = client.get("/profile")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Spending by category" in html
    assert "No spending to show yet." in html
    assert "breakdown-list" not in html
    assert "breakdown-row" not in html


# ------------------------------------------------------------ app wiring ---

def test_hardcoded_profile_constants_are_gone(app):
    import app as app_module

    for name in ("PROFILE_STATS", "PROFILE_TRANSACTIONS", "PROFILE_CATEGORIES"):
        assert not hasattr(app_module, name)


def test_app_py_contains_no_sql():
    source = APP_PATH.read_text(encoding="utf-8")
    for token in ("SELECT ", "INSERT ", "UPDATE ", ".execute("):
        assert token not in source
