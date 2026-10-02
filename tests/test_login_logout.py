import pytest

from database import db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
INVALID_ERROR = "Invalid email or password"
REQUIRED_ERROR = "Email and password are required"
SIGNED_OUT_FLASH = "You have been signed out"


def post_login(client, **overrides):
    form = {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    return client.post("/login", data={**form, **overrides})


def demo_user_id():
    return db.get_user_by_email(DEMO_EMAIL)["id"]


def test_get_login_renders_form(client):
    response = client.get("/login")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<form" in html
    assert 'action="/login"' in html
    assert "auth-error" not in html


def test_demo_login_redirects_and_starts_session(client):
    response = post_login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")

    with client.session_transaction() as sess:
        assert sess["user_id"] == demo_user_id()
        assert isinstance(sess["user_id"], int)
        assert set(sess.keys()) == {"user_id"}


def test_navbar_shows_name_and_sign_out_after_login(client):
    post_login(client)
    html = client.get("/").get_data(as_text=True)
    assert "Demo User" in html
    assert "Sign out" in html
    assert "Get started" not in html


def test_navbar_shows_guest_links_when_signed_out(client):
    html = client.get("/").get_data(as_text=True)
    assert "Sign in" in html
    assert "Get started" in html
    assert "Sign out" not in html


def test_email_is_trimmed_and_case_insensitive(client):
    response = post_login(client, email="  Demo@Spendly.com ")
    assert response.status_code == 302


def test_newly_created_user_can_log_in(client):
    db.create_user("Asha Rao", "asha@example.com", "s3cretpass")
    response = post_login(client, email="asha@example.com", password="s3cretpass")
    assert response.status_code == 302
    html = client.get("/").get_data(as_text=True)
    assert "Asha Rao" in html


def test_wrong_password_and_unknown_email_give_identical_error(client):
    wrong_password = post_login(client, password="not-the-password")
    unknown_email = post_login(client, email="nobody@example.com")

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert INVALID_ERROR in wrong_password.get_data(as_text=True)
    assert INVALID_ERROR in unknown_email.get_data(as_text=True)

    with client.session_transaction() as sess:
        assert "user_id" not in sess


@pytest.mark.parametrize(
    "form",
    [
        {"email": "", "password": DEMO_PASSWORD},
        {"email": "   ", "password": DEMO_PASSWORD},
        {"email": DEMO_EMAIL, "password": ""},
        {"email": "", "password": ""},
        {},
        {"email": DEMO_EMAIL},
        {"password": DEMO_PASSWORD},
    ],
)
def test_missing_fields_return_400(client, form):
    response = client.post("/login", data=form)
    assert response.status_code == 400
    assert REQUIRED_ERROR in response.get_data(as_text=True)
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_failed_login_keeps_email_and_never_echoes_password(client):
    response = post_login(client, password="not-the-password")
    html = response.get_data(as_text=True)
    assert f'value="{DEMO_EMAIL}"' in html
    assert "not-the-password" not in html


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_signed_in_user_is_redirected_from_auth_pages(client, path):
    post_login(client)
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_signed_in_post_login_redirects_without_re_authenticating(client):
    post_login(client)
    response = post_login(client, password="not-the-password")
    assert response.status_code == 302


def test_get_logout_while_signed_in_redirects_home_and_keeps_session(client):
    post_login(client)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert not response.headers["Location"].endswith("/login")

    with client.session_transaction() as sess:
        assert sess["user_id"] == demo_user_id()


def test_sign_out_button_is_a_post_form(client):
    post_login(client)
    html = client.get("/").get_data(as_text=True)
    assert 'method="POST" action="/logout"' in html


def test_logout_clears_session_and_flashes(client):
    post_login(client)
    response = client.post("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    with client.session_transaction() as sess:
        assert "user_id" not in sess

    html = client.get("/login").get_data(as_text=True)
    assert SIGNED_OUT_FLASH in html
    assert "Sign out" not in html
    assert "Get started" in html


@pytest.mark.parametrize("method", ["get", "post"])
def test_logout_while_signed_out_redirects_quietly(client, method):
    response = getattr(client, method)("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    html = client.get("/login").get_data(as_text=True)
    assert SIGNED_OUT_FLASH not in html


def test_stale_session_is_treated_as_signed_out(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99999

    html = client.get("/").get_data(as_text=True)
    assert "Sign in" in html
    assert "Sign out" not in html

    with client.session_transaction() as sess:
        assert "user_id" not in sess

    with client.session_transaction() as sess:
        sess["user_id"] = 99999
    assert client.get("/login").status_code == 200


def test_login_discards_pre_existing_session_data(client):
    with client.session_transaction() as sess:
        sess["planted"] = "attacker-value"

    post_login(client)

    with client.session_transaction() as sess:
        assert "planted" not in sess
        assert "user_id" in sess


def test_get_user_by_id(app):
    user_id = demo_user_id()
    assert db.get_user_by_id(user_id)["email"] == DEMO_EMAIL
    assert db.get_user_by_id(99999) is None
    assert db.get_user_by_id(None) is None


def test_stub_routes_are_unchanged(client):
    assert "coming in Step 3" not in client.get("/logout").get_data(as_text=True)
    assert "Step 7" not in client.get("/expenses/add").get_data(as_text=True)
    assert "Step 8" in client.get("/expenses/1/edit").get_data(as_text=True)
    assert "Step 9" in client.get("/expenses/1/delete").get_data(as_text=True)


@pytest.mark.parametrize("path", ["/", "/register", "/terms", "/privacy"])
def test_existing_pages_still_load(client, path):
    assert client.get(path).status_code == 200
