"""Tests for the profile page's date-range filter (Step 6)."""
from datetime import date, timedelta

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


def _add_expense(user_id, amount, category, expense_date, description="x"):
    import database.db as db

    conn = db.get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, expense_date, description),
            )
    finally:
        conn.close()


def _demo_id():
    import database.db as db

    return db.get_user_by_email(DEMO_EMAIL)["id"]


def _new_user(name="Fresh User", email="fresh@example.com", password="secret123"):
    import database.db as db

    return db.create_user(name, email, password)


def _login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


# ------------------------------------------------------ db.py helpers ---

def test_get_expense_summary_respects_date_range(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 100.0, "Food", "2026-01-05")
    _add_expense(uid, 200.0, "Bills", "2026-02-10")
    _add_expense(uid, 300.0, "Shopping", "2026-03-15")

    filtered = db.get_expense_summary(uid, start_date="2026-02-01", end_date="2026-02-28")
    assert filtered == {
        "total_spent": 200.0,
        "transaction_count": 1,
        "top_category": "Bills",
    }


def test_get_expense_summary_range_boundaries_are_inclusive(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 10.0, "Food", "2026-01-01")
    _add_expense(uid, 20.0, "Food", "2026-01-31")
    _add_expense(uid, 30.0, "Food", "2026-02-01")

    filtered = db.get_expense_summary(uid, start_date="2026-01-01", end_date="2026-01-31")
    assert filtered["total_spent"] == 30.0
    assert filtered["transaction_count"] == 2


def test_get_expense_summary_no_range_matches_step5_behaviour(app):
    import database.db as db

    assert db.get_expense_summary(_demo_id()) == db.get_expense_summary(
        _demo_id(), start_date=None, end_date=None
    )


def test_get_expense_summary_one_sided_range_is_ignored(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 10.0, "Food", "2026-01-01")
    _add_expense(uid, 20.0, "Food", "2026-06-01")

    # Only one bound given -> both are ignored, same as no filter at all.
    with_only_from = db.get_expense_summary(uid, start_date="2026-01-01", end_date=None)
    with_only_to = db.get_expense_summary(uid, start_date=None, end_date="2026-01-01")
    unfiltered = db.get_expense_summary(uid)
    assert with_only_from == with_only_to == unfiltered
    assert unfiltered["transaction_count"] == 2


def test_get_recent_expenses_respects_date_range(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 10.0, "Food", "2026-01-05", "outside")
    _add_expense(uid, 20.0, "Food", "2026-02-10", "inside")

    rows = db.get_recent_expenses(uid, start_date="2026-02-01", end_date="2026-02-28")
    assert [row["description"] for row in rows] == ["inside"]


def test_get_recent_expenses_no_range_matches_step5_behaviour(app):
    import database.db as db

    assert db.get_recent_expenses(_demo_id()) == db.get_recent_expenses(
        _demo_id(), start_date=None, end_date=None
    )


def test_get_category_breakdown_respects_date_range(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 100.0, "Food", "2026-01-05")
    _add_expense(uid, 200.0, "Bills", "2026-02-10")

    breakdown = db.get_category_breakdown(uid, start_date="2026-02-01", end_date="2026-02-28")
    assert breakdown == [{"name": "Bills", "amount": 200.0, "percent": 100}]


def test_get_category_breakdown_empty_range_is_empty_list(app):
    import database.db as db

    uid = _new_user()
    _add_expense(uid, 100.0, "Food", "2026-01-05")

    breakdown = db.get_category_breakdown(uid, start_date="2026-06-01", end_date="2026-06-30")
    assert breakdown == []


def test_get_category_breakdown_no_range_matches_step5_behaviour(app):
    import database.db as db

    assert db.get_category_breakdown(_demo_id()) == db.get_category_breakdown(
        _demo_id(), start_date=None, end_date=None
    )


# ------------------------------------------------------------ route ---

def test_unfiltered_profile_matches_step5(app, client):
    _login(client)
    unfiltered = client.get("/profile").get_data(as_text=True)
    explicit_all_time = client.get("/profile", query_string={}).get_data(as_text=True)
    assert unfiltered == explicit_all_time


def test_this_month_preset_filters_all_sections(app, client):
    uid = _new_user()
    today = date.today()
    last_month = (today.replace(day=1) - timedelta(days=1)).isoformat()
    _add_expense(uid, 999.0, "Shopping", last_month, "OLD-MONTH")
    _add_expense(uid, 50.0, "Food", today.isoformat(), "THIS-MONTH")
    _login(client, "fresh@example.com", "secret123")

    date_from = today.replace(day=1).isoformat()
    date_to = today.isoformat()
    response = client.get(
        "/profile", query_string={"date_from": date_from, "date_to": date_to}
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "THIS-MONTH" in html
    assert "OLD-MONTH" not in html
    assert "₹50.00" in html


def test_all_time_preset_shows_full_history(app, client):
    _login(client)
    response = client.get("/profile", query_string={"date_from": "", "date_to": ""})
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert html.count("tx-row") == 8


def test_valid_custom_range_filters_all_three_sections(app, client):
    uid = _new_user()
    _add_expense(uid, 100.0, "Food", "2026-01-05", "JAN")
    _add_expense(uid, 200.0, "Bills", "2026-03-10", "MAR")
    _login(client, "fresh@example.com", "secret123")

    response = client.get(
        "/profile", query_string={"date_from": "2026-01-01", "date_to": "2026-01-31"}
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "JAN" in html
    assert "MAR" not in html
    assert "₹100.00" in html
    assert html.count("tx-row") == 1
    assert html.count("breakdown-row") == 1


def test_reversed_range_flashes_error_and_falls_back(app, client):
    _login(client)
    response = client.get(
        "/profile", query_string={"date_from": "2026-06-01", "date_to": "2026-01-01"}
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Start date must be before end date." in html
    # Falls back to unfiltered: all 8 seeded demo rows show.
    assert html.count("tx-row") == 8


def test_malformed_date_does_not_crash_and_falls_back(app, client):
    _login(client)
    response = client.get(
        "/profile", query_string={"date_from": "not-a-date", "date_to": "2026-01-01"}
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert html.count("tx-row") == 8


def test_empty_result_range_shows_zero_state_without_errors(app, client):
    _login(client)
    response = client.get(
        "/profile", query_string={"date_from": "1999-01-01", "date_to": "1999-01-31"}
    )
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "₹0.00" in html
    assert "No transactions yet." in html
    assert "No spending to show yet." in html


def test_active_preset_button_is_highlighted(app, client):
    _login(client)
    today = date.today()
    response = client.get(
        "/profile",
        query_string={
            "date_from": today.replace(day=1).isoformat(),
            "date_to": today.isoformat(),
        },
    )
    html = response.get_data(as_text=True)
    assert "filter-preset-active" in html
    assert 'This Month</a>' in html.split("filter-preset-active")[1][:200]


def test_all_time_preset_link_has_no_query_params(app, client):
    _login(client)
    response = client.get("/profile")
    html = response.get_data(as_text=True)
    assert '<a href="/profile"' in html
    assert "All Time</a>" in html


def test_custom_range_fields_prefill_active_values(app, client):
    _login(client)
    response = client.get(
        "/profile", query_string={"date_from": "2026-01-01", "date_to": "2026-01-31"}
    )
    html = response.get_data(as_text=True)
    assert 'value="2026-01-01"' in html
    assert 'value="2026-01-31"' in html
    assert "filter-custom-active" in html


def test_inr_symbol_present_regardless_of_filter(app, client):
    _login(client)
    today = date.today()
    response = client.get(
        "/profile",
        query_string={
            "date_from": today.replace(day=1).isoformat(),
            "date_to": today.isoformat(),
        },
    )
    html = response.get_data(as_text=True)
    assert "₹" in html


def test_app_py_still_contains_no_sql():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    for token in ("SELECT ", "INSERT ", "UPDATE ", ".execute("):
        assert token not in source
