"""Tests for the Edit Expense feature (Step 8).

Spec: .claude/specs/08-edit-expense.md
"""

import pytest

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
OTHER_EMAIL = "fresh@example.com"
OTHER_PASSWORD = "secret123"

ORIGINAL = {
    "amount": 123.45,
    "category": "Transport",
    "date": "2026-03-10",
    "description": "ORIGINAL-DESC",
}

VALID_FORM = {
    "amount": "99.99",
    "category": "Food",
    "date": "2026-04-05",
    "description": "UPDATED-DESC",
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


def _count():
    import database.db as db

    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def _assert_unchanged(expense_id, **overrides):
    expected = {**ORIGINAL, **overrides}
    row = _row(expense_id)
    assert row["amount"] == pytest.approx(expected["amount"])
    assert row["category"] == expected["category"]
    assert row["date"] == expected["date"]
    assert row["description"] == expected["description"]


# --------------------------------------------------------- auth guard ---


class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, app, client):
        eid = _make_expense()
        response = client.get(f"/expenses/{eid}/edit")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_post_logged_out_redirects_and_changes_nothing(self, app, client):
        eid = _make_expense()
        response = client.post(f"/expenses/{eid}/edit", data=VALID_FORM)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        _assert_unchanged(eid)


# ------------------------------------------------------------- GET form ---


class TestGetForm:
    def test_get_returns_200_and_prefills_values(self, app, client):
        eid = _make_expense()
        _login(client)
        response = client.get(f"/expenses/{eid}/edit")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "123.45" in html, "amount should be pre-filled"
        assert "2026-03-10" in html, "date should be pre-filled"
        assert "ORIGINAL-DESC" in html, "description should be pre-filled"
        assert "Transport" in html

    def test_form_lists_all_categories(self, app, client):
        import database.db as db

        eid = _make_expense()
        _login(client)
        html = client.get(f"/expenses/{eid}/edit").get_data(as_text=True)
        assert len(db.CATEGORIES) == 7
        for category in db.CATEGORIES:
            assert category in html, f"expected category {category!r} in form"

    def test_current_category_is_selected(self, app, client):
        eid = _make_expense()
        _login(client)
        html = client.get(f"/expenses/{eid}/edit").get_data(as_text=True)
        assert "selected" in html

    def test_get_does_not_modify_row_or_count(self, app, client):
        eid = _make_expense()
        before = _count()
        _login(client)
        client.get(f"/expenses/{eid}/edit")
        assert _count() == before
        _assert_unchanged(eid)


# ----------------------------------------------------------- happy path ---


class TestValidSubmission:
    def test_valid_post_redirects_to_profile(self, app, client):
        eid = _make_expense()
        _login(client)
        response = client.post(f"/expenses/{eid}/edit", data=VALID_FORM)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/profile")

    def test_valid_post_updates_row_without_adding_one(self, app, client):
        eid = _make_expense()
        before = _count()
        _login(client)
        client.post(f"/expenses/{eid}/edit", data=VALID_FORM)
        assert _count() == before, "edit must not create a new row"
        row = _row(eid)
        assert row["user_id"] == _demo_id()
        assert row["amount"] == pytest.approx(99.99)
        assert row["category"] == "Food"
        assert row["date"] == "2026-04-05"
        assert row["description"] == "UPDATED-DESC"

    def test_success_flash_shown_after_redirect(self, app, client):
        eid = _make_expense()
        _login(client)
        response = client.post(
            f"/expenses/{eid}/edit", data=VALID_FORM, follow_redirects=True
        )
        assert response.status_code == 200
        assert "Expense updated" in response.get_data(as_text=True)

    def test_updated_description_visible_on_profile(self, app, client):
        eid = _make_expense()
        _login(client)
        client.post(f"/expenses/{eid}/edit", data=VALID_FORM)
        html = client.get("/profile").get_data(as_text=True)
        assert "UPDATED-DESC" in html
        assert "ORIGINAL-DESC" not in html

    def test_blank_description_stored_as_null_and_shown_empty(self, app, client):
        eid = _make_expense()
        _login(client)
        response = client.post(
            f"/expenses/{eid}/edit", data={**VALID_FORM, "description": ""}
        )
        assert response.status_code == 302
        assert _row(eid)["description"] is None
        html = client.get(f"/expenses/{eid}/edit").get_data(as_text=True)
        assert "None" not in html, "NULL description must render as empty"

    def test_whitespace_description_stored_as_null(self, app, client):
        eid = _make_expense()
        _login(client)
        client.post(f"/expenses/{eid}/edit", data={**VALID_FORM, "description": "   "})
        assert _row(eid)["description"] is None

    def test_description_exactly_200_chars_succeeds(self, app, client):
        eid = _make_expense()
        _login(client)
        response = client.post(
            f"/expenses/{eid}/edit", data={**VALID_FORM, "description": "x" * 200}
        )
        assert response.status_code == 302
        assert _row(eid)["description"] == "x" * 200

    def test_only_target_row_changes(self, app, client):
        eid = _make_expense()
        other = _make_expense(description="NEIGHBOUR")
        _login(client)
        client.post(f"/expenses/{eid}/edit", data=VALID_FORM)
        _assert_unchanged(other, description="NEIGHBOUR")

    def test_cancel_link_points_to_profile(self, app, client):
        eid = _make_expense()
        _login(client)
        html = client.get(f"/expenses/{eid}/edit").get_data(as_text=True)
        assert 'href="/profile"' in html


# ----------------------------------------------------------- validation ---


class TestValidation:
    @pytest.mark.parametrize("amount", ["0", "-5", "abc", ""])
    def test_invalid_amount_returns_400_and_row_unchanged(self, app, client, amount):
        eid = _make_expense()
        _login(client)
        response = client.post(
            f"/expenses/{eid}/edit", data={**VALID_FORM, "amount": amount}
        )
        assert response.status_code == 400
        assert "Enter an amount greater than 0" in response.get_data(as_text=True)
        _assert_unchanged(eid)

    @pytest.mark.parametrize("category", ["Crypto", ""])
    def test_invalid_category_returns_400_and_row_unchanged(
        self, app, client, category
    ):
        eid = _make_expense()
        _login(client)
        response = client.post(
            f"/expenses/{eid}/edit", data={**VALID_FORM, "category": category}
        )
        assert response.status_code == 400
        assert "Choose a valid category" in response.get_data(as_text=True)
        _assert_unchanged(eid)

    @pytest.mark.parametrize("bad_date", ["", "2026-13-40", "abc"])
    def test_invalid_date_returns_400_and_row_unchanged(self, app, client, bad_date):
        eid = _make_expense()
        _login(client)
        response = client.post(
            f"/expenses/{eid}/edit", data={**VALID_FORM, "date": bad_date}
        )
        assert response.status_code == 400
        assert "Enter a valid date" in response.get_data(as_text=True)
        _assert_unchanged(eid)

    def test_description_over_200_returns_400_and_row_unchanged(self, app, client):
        eid = _make_expense()
        _login(client)
        response = client.post(
            f"/expenses/{eid}/edit", data={**VALID_FORM, "description": "x" * 201}
        )
        assert response.status_code == 400
        assert "Description must be 200 characters or fewer" in response.get_data(
            as_text=True
        )
        _assert_unchanged(eid)

    def test_submitted_values_kept_in_form_after_error(self, app, client):
        eid = _make_expense()
        _login(client)
        form = {
            "amount": "-5",
            "category": "Health",
            "date": "2026-05-06",
            "description": "KEEP-ME-TYPED",
        }
        response = client.post(f"/expenses/{eid}/edit", data=form)
        html = response.get_data(as_text=True)
        assert response.status_code == 400
        assert "KEEP-ME-TYPED" in html
        assert "2026-05-06" in html
        assert "-5" in html


# -------------------------------------------------- missing / not owned ---


class TestMissingAndForeignExpense:
    def test_get_nonexistent_id_returns_404(self, app, client):
        _login(client)
        assert client.get("/expenses/99999/edit").status_code == 404

    def test_post_nonexistent_id_returns_404(self, app, client):
        _login(client)
        before = _count()
        response = client.post("/expenses/99999/edit", data=VALID_FORM)
        assert response.status_code == 404
        assert _count() == before

    def test_get_other_users_expense_returns_404(self, app, client):
        other_id = _new_user()
        eid = _make_expense(user_id=other_id)
        _login(client)
        assert client.get(f"/expenses/{eid}/edit").status_code == 404

    def test_post_other_users_expense_returns_404_and_row_unchanged(self, app, client):
        other_id = _new_user()
        eid = _make_expense(user_id=other_id)
        _login(client)
        response = client.post(f"/expenses/{eid}/edit", data=VALID_FORM)
        assert response.status_code == 404
        _assert_unchanged(eid)
        assert _row(eid)["user_id"] == other_id

    def test_other_users_expense_not_leaked_in_404(self, app, client):
        other_id = _new_user()
        eid = _make_expense(user_id=other_id, description="SECRET-OTHER-DESC")
        _login(client)
        html = client.get(f"/expenses/{eid}/edit").get_data(as_text=True)
        assert "SECRET-OTHER-DESC" not in html


# --------------------------------------------------------- profile link ---


class TestProfileEditLink:
    def test_profile_has_edit_link_for_users_rows(self, app, client):
        eid = _make_expense()
        _login(client)
        html = client.get("/profile").get_data(as_text=True)
        assert f'href="/expenses/{eid}/edit"' in html

    def test_profile_has_no_edit_link_for_other_users_rows(self, app, client):
        other_id = _new_user()
        eid = _make_expense(user_id=other_id)
        _login(client)
        html = client.get("/profile").get_data(as_text=True)
        assert f"/expenses/{eid}/edit" not in html


# ----------------------------------------------------------- db helpers ---


class TestDbHelpers:
    def test_get_expense_by_id_returns_owned_row(self, app):
        import database.db as db

        eid = _make_expense()
        row = db.get_expense_by_id(eid, _demo_id())
        assert row is not None
        assert row["id"] == eid
        assert row["amount"] == pytest.approx(123.45)
        assert row["category"] == "Transport"
        assert row["date"] == "2026-03-10"
        assert row["description"] == "ORIGINAL-DESC"

    def test_get_expense_by_id_returns_empty_string_for_null_description(self, app):
        import database.db as db

        eid = _make_expense(description="")
        row = db.get_expense_by_id(eid, _demo_id())
        assert row["description"] == ""

    def test_get_expense_by_id_returns_none_for_other_users_id(self, app):
        import database.db as db

        other_id = _new_user()
        eid = _make_expense(user_id=other_id)
        assert db.get_expense_by_id(eid, _demo_id()) is None

    def test_get_expense_by_id_returns_none_for_missing_id(self, app):
        import database.db as db

        assert db.get_expense_by_id(99999, _demo_id()) is None

    def test_update_expense_returns_true_and_updates_owned_row(self, app):
        import database.db as db

        eid = _make_expense()
        result = db.update_expense(eid, _demo_id(), 5.5, "Bills", "2026-01-02", "new")
        assert result is True
        row = _row(eid)
        assert row["amount"] == pytest.approx(5.5)
        assert row["category"] == "Bills"
        assert row["date"] == "2026-01-02"
        assert row["description"] == "new"

    def test_update_expense_blank_description_stored_as_null(self, app):
        import database.db as db

        eid = _make_expense()
        assert db.update_expense(eid, _demo_id(), 5, "Bills", "2026-01-02", "  ")
        assert _row(eid)["description"] is None

    def test_update_expense_returns_false_for_other_users_id(self, app):
        import database.db as db

        other_id = _new_user()
        eid = _make_expense(user_id=other_id)
        result = db.update_expense(eid, _demo_id(), 5, "Bills", "2026-01-02", "hack")
        assert result is False
        _assert_unchanged(eid)

    def test_update_expense_returns_false_for_missing_id(self, app):
        import database.db as db

        assert (
            db.update_expense(99999, _demo_id(), 5, "Bills", "2026-01-02", "x") is False
        )

    def test_get_recent_expenses_rows_include_id(self, app):
        import database.db as db

        eid = _make_expense()
        rows = db.get_recent_expenses(_demo_id())
        assert rows, "expected at least one recent expense"
        assert all("id" in r for r in rows)
        assert eid in [r["id"] for r in rows]


# ------------------------------------------------- delete still a stub ---


class TestDeleteStillPlaceholder:
    def test_delete_route_returns_step_9_placeholder(self, app, client):
        eid = _make_expense()
        _login(client)
        response = client.get(f"/expenses/{eid}/delete")
        assert response.status_code == 200
        assert "Step 9" in response.get_data(as_text=True)
        assert _row(eid) is not None, "placeholder must not delete anything"
