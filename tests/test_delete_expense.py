"""Tests for the Delete Expense feature (Step 9).

Spec: .claude/specs/09-delete-expenses.md
Plan: .claude/plans/09-delete-expenses-plan.md (section 9)
"""

import re

import pytest

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
OTHER_EMAIL = "fresh@example.com"
OTHER_PASSWORD = "secret123"

ORIGINAL = {
    "amount": 1234.50,
    "category": "Transport",
    "date": "2026-03-10",
    "description": "ORIGINAL-DESC",
}


def _login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def _new_user(name="Fresh User", email=OTHER_EMAIL, password=OTHER_PASSWORD):
    import database.db as db

    return db.create_user(name, email, password)


def _demo_id():
    import database.db as db

    return db.get_user_by_email(DEMO_EMAIL)["id"]


def _make_expense(user_id=None, **overrides):
    import database.db as db

    data = {**ORIGINAL, **overrides}
    if user_id is None:
        user_id = _demo_id()
    return db.create_expense(
        user_id, data["amount"], data["category"], data["date"], data["description"]
    )


def _row(expense_id):
    import database.db as db

    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _clear_expenses(user_id):
    """Remove all seeded expenses for a user so profile assertions are exact."""
    import database.db as db

    conn = db.get_db()
    try:
        with conn:
            conn.execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
    finally:
        conn.close()


def _delete_url(expense_id):
    return f"/expenses/{expense_id}/delete"


def _profile_html(client):
    response = client.get("/profile")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def _tx_count_text(html):
    match = re.search(r"Transactions\s*</span>\s*<span[^>]*>\s*(\d+)\s*</span>", html)
    assert match, "could not find transaction count on profile"
    return int(match.group(1))


# --------------------------------------------------------- auth guard ---


class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, app, client):
        eid = _make_expense()
        response = client.get(_delete_url(eid))
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        assert _row(eid) is not None

    def test_post_logged_out_redirects_and_keeps_row(self, app, client):
        eid = _make_expense()
        response = client.post(_delete_url(eid))
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        assert _row(eid) is not None, "logged-out POST must not delete"


# ------------------------------------------------- GET confirmation page ---


class TestConfirmationPage:
    def test_get_returns_200_with_expense_details(self, app, client):
        eid = _make_expense()
        _login(client)
        response = client.get(_delete_url(eid))
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "2026-03-10" in html
        assert "ORIGINAL-DESC" in html
        assert "Transport" in html
        assert "₹1,234.50" in html

    def test_get_blank_description_shows_fallback(self, app, client):
        eid = _make_expense(description="")
        _login(client)
        html = client.get(_delete_url(eid)).get_data(as_text=True)
        assert "No description" in html

    def test_get_has_post_form_delete_button_and_cancel_link(self, app, client):
        eid = _make_expense()
        _login(client)
        html = client.get(_delete_url(eid)).get_data(as_text=True)
        assert re.search(r"<form[^>]*method=\"post\"", html, re.I)
        assert f'action="{_delete_url(eid)}"' in html
        assert "Delete expense" in html
        assert "Cancel" in html
        cancel = re.search(r'<a[^>]*href="([^"]*)"[^>]*>\s*Cancel\s*</a>', html)
        assert cancel, "Cancel link not found"
        assert cancel.group(1) == "/profile"

    def test_get_does_not_delete_row(self, app, client):
        eid = _make_expense()
        _login(client)
        client.get(_delete_url(eid))
        assert _row(eid) is not None, "GET must never delete"
        assert "ORIGINAL-DESC" in _profile_html(client)


# ------------------------------------------------------- POST deletion ---


class TestPostDelete:
    def test_post_redirects_to_profile_and_removes_row(self, app, client):
        eid = _make_expense()
        _login(client)
        response = client.post(_delete_url(eid))
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")
        assert _row(eid) is None

    def test_post_follow_shows_flash_and_row_gone(self, app, client):
        eid = _make_expense()
        _login(client)
        response = client.post(_delete_url(eid), follow_redirects=True)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Expense deleted" in html
        assert "ORIGINAL-DESC" not in html

    def test_post_only_removes_target_row(self, app, client):
        keep = _make_expense(description="KEEP-ME", amount=5)
        gone = _make_expense(description="GONE-ME", amount=6)
        _login(client)
        client.post(_delete_url(gone))
        assert _row(gone) is None
        assert _row(keep) is not None

    def test_profile_stats_update_after_delete(self, app, client):
        uid = _demo_id()
        _clear_expenses(uid)
        _make_expense(amount=100, category="Food", description="FOOD-ONE")
        victim = _make_expense(amount=50, category="Bills", description="BILL-ONE")
        _login(client)

        before = _profile_html(client)
        assert _tx_count_text(before) == 2
        assert "₹150.00" in before

        client.post(_delete_url(victim))
        after = _profile_html(client)
        assert _tx_count_text(after) == 1
        assert "₹100.00" in after
        assert "₹150.00" not in after
        assert "BILL-ONE" not in after

    def test_deleting_only_expense_in_category_removes_it_from_breakdown(
        self, app, client
    ):
        uid = _demo_id()
        _clear_expenses(uid)
        _make_expense(amount=100, category="Food", description="FOOD-ONE")
        victim = _make_expense(amount=50, category="Bills", description="BILL-ONE")
        _login(client)

        before = _profile_html(client)
        assert re.search(
            r'class="breakdown-name">\s*Bills\s*<', before
        ), "Bills should be in breakdown before delete"

        client.post(_delete_url(victim))
        after = _profile_html(client)
        assert not re.search(r'class="breakdown-name">\s*Bills\s*<', after)
        assert re.search(r'class="breakdown-name">\s*Food\s*<', after)

    def test_deleting_last_expense_shows_empty_state(self, app, client):
        uid = _demo_id()
        _clear_expenses(uid)
        eid = _make_expense(amount=77)
        _login(client)

        response = client.post(_delete_url(eid), follow_redirects=True)
        html = response.get_data(as_text=True)
        assert "No transactions yet." in html
        assert _tx_count_text(html) == 0
        assert "₹0.00" in html


# ------------------------------------------------------------ 404 cases ---


class TestNotFound:
    @pytest.mark.parametrize("method", ["get", "post"])
    def test_nonexistent_id_returns_404(self, app, client, method):
        _login(client)
        response = getattr(client, method)(_delete_url(99999))
        assert response.status_code == 404

    @pytest.mark.parametrize("method", ["get", "post"])
    def test_other_users_expense_returns_404_and_survives(self, app, client, method):
        owner_id = _new_user()
        eid = _make_expense(user_id=owner_id)
        _login(client)  # demo user is not the owner
        response = getattr(client, method)(_delete_url(eid))
        assert response.status_code == 404
        assert _row(eid) is not None, "another user's row must survive"

    def test_second_post_returns_404(self, app, client):
        eid = _make_expense()
        _login(client)
        assert client.post(_delete_url(eid)).status_code == 302
        assert client.post(_delete_url(eid)).status_code == 404


# ------------------------------------------------ profile Delete links ---


class TestProfileDeleteLinks:
    def test_each_row_has_delete_link_to_own_id(self, app, client):
        uid = _demo_id()
        _clear_expenses(uid)
        ids = [
            _make_expense(description="ROW-A", amount=1),
            _make_expense(description="ROW-B", amount=2),
            _make_expense(description="ROW-C", amount=3),
        ]
        _login(client)
        html = _profile_html(client)
        hrefs = re.findall(r'<a[^>]*href="([^"]*)"[^>]*class="tx-delete-link"', html)
        for eid in ids:
            assert _delete_url(eid) in hrefs, f"missing Delete link for {eid}"
        assert len(hrefs) == len(ids)


# ------------------------------------------------------------ db helper ---


class TestDbDeleteExpense:
    def test_returns_true_and_removes_row_for_owner(self, app):
        import database.db as db

        uid = _demo_id()
        eid = _make_expense()
        assert db.delete_expense(eid, uid) is True
        assert _row(eid) is None

    def test_returns_false_for_wrong_user_and_keeps_row(self, app):
        import database.db as db

        other = _new_user()
        eid = _make_expense()
        assert db.delete_expense(eid, other) is False
        assert _row(eid) is not None

    def test_returns_false_for_missing_id(self, app):
        import database.db as db

        assert db.delete_expense(99999, _demo_id()) is False

    def test_only_removes_owner_row(self, app):
        import database.db as db

        uid = _demo_id()
        other = _new_user()
        mine = _make_expense(user_id=uid, description="MINE")
        theirs = _make_expense(user_id=other, description="THEIRS")
        assert db.delete_expense(mine, uid) is True
        assert _row(mine) is None
        assert _row(theirs) is not None

    def test_second_delete_returns_false(self, app):
        import database.db as db

        uid = _demo_id()
        eid = _make_expense()
        assert db.delete_expense(eid, uid) is True
        assert db.delete_expense(eid, uid) is False


# ----------------------------------------------------------- smoke tests ---


class TestOtherExpenseRoutesStillWork:
    def test_add_expense_page_loads(self, app, client):
        _login(client)
        assert client.get("/expenses/add").status_code == 200

    def test_edit_expense_page_loads(self, app, client):
        eid = _make_expense()
        _login(client)
        response = client.get(f"/expenses/{eid}/edit")
        assert response.status_code == 200
        assert "ORIGINAL-DESC" in response.get_data(as_text=True)
