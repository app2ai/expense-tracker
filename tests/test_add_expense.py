"""Tests for the Add Expense feature (Step 7).

Spec: .claude/specs/07-add-expense.md
Plan: .claude/plans/07-add-expense-plan.md (section 8 lists these cases)
"""
from datetime import date

import pytest

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


def _login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def _new_user(name="Fresh User", email="fresh@example.com", password="secret123"):
    import database.db as db

    return db.create_user(name, email, password)


def _demo_id():
    import database.db as db

    return db.get_user_by_email(DEMO_EMAIL)["id"]


def _expense_count():
    import database.db as db

    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def _last_expense():
    import database.db as db

    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT * FROM expenses ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


VALID_FORM = {
    "amount": "250.50",
    "category": "Food",
    "date": date.today().isoformat(),
    "description": "Lunch",
}


# --------------------------------------------------------- auth guard ---

class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, app, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_post_logged_out_redirects_to_login_and_inserts_nothing(self, app, client):
        before = _expense_count()
        response = client.post("/expenses/add", data=VALID_FORM)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        assert _expense_count() == before, "logged-out POST must not insert a row"


# ------------------------------------------------------------- GET form ---

class TestGetForm:
    def test_logged_in_get_returns_200(self, app, client):
        _login(client)
        response = client.get("/expenses/add")
        assert response.status_code == 200

    def test_form_lists_all_seven_categories(self, app, client):
        import database.db as db

        _login(client)
        html = client.get("/expenses/add").get_data(as_text=True)
        assert len(db.CATEGORIES) == 7
        for category in db.CATEGORIES:
            assert category in html, f"expected category {category!r} in the form"

    def test_date_prefilled_with_today(self, app, client):
        _login(client)
        html = client.get("/expenses/add").get_data(as_text=True)
        today = date.today().isoformat()
        assert f'value="{today}"' in html

    def test_profile_has_add_expense_link(self, app, client):
        _login(client)
        html = client.get("/profile").get_data(as_text=True)
        assert 'href="/expenses/add"' in html


# ----------------------------------------------------------- happy path ---

class TestValidSubmission:
    def test_valid_post_redirects_to_profile(self, app, client):
        _login(client)
        response = client.post("/expenses/add", data=VALID_FORM)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

    def test_valid_post_inserts_exactly_one_row_with_correct_fields(self, app, client):
        before = _expense_count()
        _login(client)
        client.post("/expenses/add", data=VALID_FORM)
        assert _expense_count() == before + 1

        row = _last_expense()
        assert row["user_id"] == _demo_id()
        assert row["amount"] == pytest.approx(250.50)
        assert row["category"] == "Food"
        assert row["date"] == date.today().isoformat()
        assert row["description"] == "Lunch"

    def test_valid_post_shows_success_flash_on_profile(self, app, client):
        _login(client)
        response = client.post("/expenses/add", data=VALID_FORM, follow_redirects=True)
        html = response.get_data(as_text=True)
        assert "Expense added" in html
        assert "auth-success" in html

    def test_valid_post_row_appears_in_profile_recent_transactions(self, app, client):
        _login(client)
        client.post(
            "/expenses/add",
            data={**VALID_FORM, "description": "UNIQUE-LUNCH-MARKER"},
            follow_redirects=True,
        )
        html = client.get("/profile").get_data(as_text=True)
        assert "UNIQUE-LUNCH-MARKER" in html

    def test_blank_description_succeeds_and_is_stored_as_null(self, app, client):
        before = _expense_count()
        _login(client)
        form = {**VALID_FORM, "description": ""}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 302
        assert _expense_count() == before + 1
        row = _last_expense()
        assert row["description"] is None

    def test_whitespace_only_description_is_stored_as_null(self, app, client):
        _login(client)
        form = {**VALID_FORM, "description": "   "}
        client.post("/expenses/add", data=form)
        row = _last_expense()
        assert row["description"] is None

    def test_description_exactly_200_chars_succeeds(self, app, client):
        _login(client)
        form = {**VALID_FORM, "description": "x" * 200}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 302
        row = _last_expense()
        assert row["description"] == "x" * 200

    def test_amount_rounded_to_two_decimal_places(self, app, client):
        _login(client)
        form = {**VALID_FORM, "amount": "10.005"}
        client.post("/expenses/add", data=form)
        row = _last_expense()
        assert row["amount"] == pytest.approx(round(10.005, 2))

    def test_cancel_link_points_to_profile(self, app, client):
        _login(client)
        html = client.get("/expenses/add").get_data(as_text=True)
        assert 'href="/profile"' in html

    def test_get_never_inserts_a_row(self, app, client):
        before = _expense_count()
        _login(client)
        client.get("/expenses/add")
        assert _expense_count() == before


# ----------------------------------------------------------- validation ---

class TestAmountValidation:
    @pytest.mark.parametrize(
        "amount",
        ["0", "-5", "abc", "", "nan", "inf", "-inf", "0.001"],
    )
    def test_invalid_amount_returns_400_and_inserts_nothing(self, app, client, amount):
        before = _expense_count()
        _login(client)
        form = {**VALID_FORM, "amount": amount}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 400
        assert "Enter an amount greater than 0" in response.get_data(as_text=True)
        assert _expense_count() == before


class TestCategoryValidation:
    def test_tampered_category_returns_400_and_inserts_nothing(self, app, client):
        before = _expense_count()
        _login(client)
        form = {**VALID_FORM, "category": "Crypto"}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 400
        assert "Choose a valid category" in response.get_data(as_text=True)
        assert _expense_count() == before

    def test_blank_category_returns_400_and_inserts_nothing(self, app, client):
        before = _expense_count()
        _login(client)
        form = {**VALID_FORM, "category": ""}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 400
        assert _expense_count() == before


class TestDateValidation:
    @pytest.mark.parametrize("bad_date", ["", "2026-13-40", "abc", "not-a-date"])
    def test_invalid_date_returns_400_and_inserts_nothing(self, app, client, bad_date):
        before = _expense_count()
        _login(client)
        form = {**VALID_FORM, "date": bad_date}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 400
        assert "Enter a valid date" in response.get_data(as_text=True)
        assert _expense_count() == before


class TestDescriptionValidation:
    def test_description_over_200_chars_returns_400_and_inserts_nothing(self, app, client):
        before = _expense_count()
        _login(client)
        form = {**VALID_FORM, "description": "x" * 201}
        response = client.post("/expenses/add", data=form)
        assert response.status_code == 400
        assert (
            "Description must be 200 characters or fewer"
            in response.get_data(as_text=True)
        )
        assert _expense_count() == before


class TestFormRepopulation:
    def test_submitted_values_are_echoed_back_after_error(self, app, client):
        _login(client)
        form = {
            "amount": "-5",
            "category": "Food",
            "date": date.today().isoformat(),
            "description": "keep-me",
        }
        response = client.post("/expenses/add", data=form)
        html = response.get_data(as_text=True)
        assert response.status_code == 400
        assert "keep-me" in html
        assert f'value="{date.today().isoformat()}"' in html


# ------------------------------------------------------- multi-user data ---

class TestPerUserIsolation:
    def test_one_users_expense_does_not_appear_on_another_users_profile(
        self, app, client
    ):
        _new_user()
        _login(client, "fresh@example.com", "secret123")
        client.post(
            "/expenses/add",
            data={**VALID_FORM, "description": "FRESH-USER-MARKER"},
        )
        client.post("/logout")

        _login(client)
        html = client.get("/profile").get_data(as_text=True)
        assert "FRESH-USER-MARKER" not in html


class TestBackdatedExpenseFiltering:
    def test_backdated_expense_shows_only_under_matching_date_filter(
        self, app, client
    ):
        _new_user()
        _login(client, "fresh@example.com", "secret123")
        old_date = "2020-01-15"
        client.post(
            "/expenses/add",
            data={
                "amount": "42.00",
                "category": "Bills",
                "date": old_date,
                "description": "OLD-BACKDATED-MARKER",
            },
        )

        outside_range = client.get(
            "/profile",
            query_string={"date_from": "2026-01-01", "date_to": "2026-12-31"},
        ).get_data(as_text=True)
        assert "OLD-BACKDATED-MARKER" not in outside_range

        inside_range = client.get(
            "/profile",
            query_string={"date_from": "2020-01-01", "date_to": "2020-01-31"},
        ).get_data(as_text=True)
        assert "OLD-BACKDATED-MARKER" in inside_range


# ------------------------------------------ existing Step 6 flash intact ---

class TestExistingFlashStillWorks:
    def test_reversed_date_range_flash_still_renders_as_auth_error(self, app, client):
        _login(client)
        response = client.get(
            "/profile",
            query_string={"date_from": "2026-06-01", "date_to": "2026-01-01"},
        )
        html = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "Start date must be before end date." in html
        assert "auth-error" in html
