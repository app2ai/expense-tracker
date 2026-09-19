import importlib
import sqlite3

import pytest
from werkzeug.security import check_password_hash

from conftest import count_users
from database import db

DUPLICATE_ERROR = "An account with this email already exists"

VALID_FORM = {
    "name": "Asha Rao",
    "email": "asha@example.com",
    "password": "s3cretpass",
}


def post_register(client, **overrides):
    return client.post("/register", data={**VALID_FORM, **overrides})


def test_get_register_renders_form(client):
    response = client.get("/register")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<form" in html
    assert "auth-error" not in html


def test_form_action_is_register(client):
    html = client.get("/register").get_data(as_text=True)
    assert 'action="/register"' in html


def test_valid_registration_redirects_to_login(client):
    before = count_users()
    response = post_register(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert count_users() == before + 1


def test_login_shows_success_message_after_registration(client):
    response = post_register(client)
    assert response.status_code == 302
    html = client.get("/login").get_data(as_text=True)
    assert "Account created — please sign in" in html
    assert "auth-success" in html


def test_password_is_hashed(client):
    post_register(client)
    user = db.get_user_by_email("asha@example.com")
    assert user["password_hash"] != VALID_FORM["password"]
    assert check_password_hash(user["password_hash"], VALID_FORM["password"])


@pytest.mark.parametrize(
    "email",
    ["demo@spendly.com", "Demo@Spendly.com", "  demo@spendly.com  "],
)
def test_duplicate_email_rejected(client, email):
    before = count_users()
    response = post_register(client, email=email)
    assert response.status_code == 400
    assert DUPLICATE_ERROR in response.get_data(as_text=True)
    assert count_users() == before


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_rejected(client, name):
    before = count_users()
    response = post_register(client, name=name)
    assert response.status_code == 400
    assert "Name is required" in response.get_data(as_text=True)
    assert count_users() == before


@pytest.mark.parametrize(
    "email", ["no-at", "@x.com", "a@", "a@nodot", "a@.com", "a@x.", "a b@x.com", ""]
)
def test_invalid_email_rejected(client, email):
    before = count_users()
    response = post_register(client, email=email)
    assert response.status_code == 400
    assert "valid email" in response.get_data(as_text=True)
    assert count_users() == before


def test_short_password_rejected(client):
    before = count_users()
    response = post_register(client, password="1234567")
    assert response.status_code == 400
    assert "at least 8 characters" in response.get_data(as_text=True)
    assert count_users() == before


def test_eight_character_password_accepted(client):
    assert post_register(client, password="12345678").status_code == 302


def test_failed_submit_keeps_name_and_email_but_not_password(client):
    response = post_register(client, password="short7!")
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    assert 'value="Asha Rao"' in html
    assert 'value="asha@example.com"' in html
    assert "short7!" not in html


def test_email_stored_trimmed_and_lowercased(client):
    post_register(client, email="  New@Example.COM ")
    user = db.get_user_by_email("new@example.com")
    assert user["email"] == "new@example.com"


def test_password_is_not_trimmed(client):
    post_register(client, password="  password1  ")
    user = db.get_user_by_email(VALID_FORM["email"])
    assert check_password_hash(user["password_hash"], "  password1  ")


def test_missing_form_fields_return_400_not_500(client):
    assert client.post("/register", data={}).status_code == 400


def test_integrity_error_race_is_handled(client, monkeypatch):
    # Simulate the pre-check missing an existing email; the UNIQUE constraint must catch it.
    monkeypatch.setattr(importlib.import_module("app"), "get_user_by_email", lambda email: None)
    before = count_users()
    response = post_register(client, email="demo@spendly.com")
    assert response.status_code == 400
    assert DUPLICATE_ERROR in response.get_data(as_text=True)
    assert count_users() == before


def test_create_user_returns_id_and_rejects_duplicates(app):
    user_id = db.create_user("Ravi", "ravi@example.com", "password123")
    assert isinstance(user_id, int)
    with pytest.raises(sqlite3.IntegrityError):
        db.create_user("Ravi Again", "ravi@example.com", "password123")


def test_get_user_by_email_unknown_returns_none(app):
    assert db.get_user_by_email("nobody@example.com") is None


@pytest.mark.parametrize("path", ["/", "/login", "/terms", "/privacy"])
def test_existing_pages_still_load(client, path):
    assert client.get(path).status_code == 200
