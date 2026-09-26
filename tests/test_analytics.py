import re
from pathlib import Path

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "analytics.html"


def post_login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def get_analytics_html(client):
    post_login(client)
    response = client.get("/analytics")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_guest_is_redirected_to_login(client):
    response = client.get("/analytics")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_stale_session_is_redirected_to_login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    response = client.get("/analytics")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_logged_in_user_gets_200(client):
    post_login(client)
    assert client.get("/analytics").status_code == 200


def test_page_title_is_analytics_spendly(client):
    html = get_analytics_html(client)
    assert "<title>Analytics — Spendly</title>" in html


def test_page_links_analytics_css(client):
    html = get_analytics_html(client)
    assert "css/analytics.css" in html


def test_shows_in_development_badge(client):
    html = get_analytics_html(client)
    assert "In development" in html


def test_shows_investment_tracking_heading(client):
    html = get_analytics_html(client)
    assert "Investment tracking" in html


def test_shows_notify_button(client):
    html = get_analytics_html(client)
    assert "Notify me when it's ready" in html
    assert "data-notify-button" in html


def test_shows_hidden_notify_confirmation(client):
    html = get_analytics_html(client)
    assert "We'll notify you when it's ready" in html
    match = re.search(r"<div[^>]*data-notify-confirmation[^>]*>", html)
    assert match, "Expected a data-notify-confirmation element"
    assert "hidden" in match.group(0), "Confirmation should start hidden"


def test_navbar_shows_analytics_link_when_logged_in(client):
    html = get_analytics_html(client)
    assert 'href="/analytics"' in html


def test_navbar_hides_analytics_link_when_logged_out(client):
    response = client.get("/")
    html = response.get_data(as_text=True)
    assert 'href="/analytics"' not in html
    assert "Analytics" not in html


def test_analytics_nav_link_is_active_on_analytics_page(client):
    html = get_analytics_html(client)
    match = re.search(r'<a href="/analytics"[^>]*>Analytics</a>', html)
    assert match, "Expected an Analytics nav link"
    assert "nav-link-active" in match.group(0)
    assert 'aria-current="page"' in match.group(0)


def test_analytics_nav_link_is_not_active_on_profile_page(client):
    post_login(client)
    html = client.get("/profile").get_data(as_text=True)
    match = re.search(r'<a href="/analytics"[^>]*>Analytics</a>', html)
    assert match, "Expected an Analytics nav link on profile page"
    assert "nav-link-active" not in match.group(0)
    assert "aria-current" not in match.group(0)


def test_analytics_template_has_no_hex_colours_or_inline_styles():
    source = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", source)
    assert "style=" not in source
