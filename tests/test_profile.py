import re
from pathlib import Path

from database import db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "profile.html"


def post_login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def get_profile_html(client):
    post_login(client)
    response = client.get("/profile")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_guest_is_redirected_to_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_stale_session_is_redirected_to_login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_logged_in_user_gets_200(client):
    post_login(client)
    assert client.get("/profile").status_code == 200


def test_user_card_shows_logged_in_users_details(client):
    db.create_user("Asha Verma", "asha@example.com", "password123")
    post_login(client, "asha@example.com", "password123")
    html = client.get("/profile").get_data(as_text=True)
    assert "Asha Verma" in html
    assert "asha@example.com" in html
    assert ">AV<" in html
    assert "Member since" in html


def test_user_name_is_escaped(client):
    db.create_user("<script>alert(1)</script>", "xss@example.com", "password123")
    post_login(client, "xss@example.com", "password123")
    html = client.get("/profile").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_summary_stats_are_shown(client):
    html = get_profile_html(client)
    assert html.count('class="stat-card"') >= 3
    for label in ("Total spent", "Transactions", "Top category"):
        assert label in html
    assert "₹5,164.25" in html
    assert "badge-bills" in html


def test_transaction_table_has_rows(client):
    html = get_profile_html(client)
    assert html.count('class="tx-row"') >= 3
    for header in ("Date", "Description", "Category", "Amount"):
        assert f">{header}</th>" in html
    assert "Groceries" in html
    assert "₹320.50" in html
    assert "badge-food" in html


def test_category_breakdown_has_categories(client):
    html = get_profile_html(client)
    assert html.count('class="breakdown-row"') >= 3
    assert html.count("<progress") >= 3
    assert "Spending by category" in html


def test_navbar_shows_username_and_logout_for_logged_in_user(client):
    html = get_profile_html(client)
    assert 'href="/profile" class="nav-user"' in html
    assert "Demo User" in html
    assert "Sign out" in html
    assert "Get started" not in html


def test_profile_template_has_no_hex_colours_or_inline_styles():
    source = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", source)
    assert "style=" not in source
