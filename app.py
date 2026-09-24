import os
import sqlite3
from calendar import monthrange
from datetime import date, datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (  # noqa: F401
    create_user,
    get_category_breakdown,
    get_db,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

# Dev-only fallback. Insecure and public: production must set SECRET_KEY.
DEV_SECRET_KEY = "dev-only-insecure-secret-key-change-me"

MIN_PASSWORD_LENGTH = 8

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", DEV_SECRET_KEY)

with app.app_context():
    init_db()
    seed_db()


def _get_current_user():
    """Return the signed-in user row, or None. Drops a stale session user id."""
    user = get_user_by_id(session.get("user_id"))
    if user is None:
        session.pop("user_id", None)
    return user


@app.context_processor
def inject_current_user():
    return {"current_user": _get_current_user()}


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


def _is_valid_email(email):
    """Simple format check: local@domain with a dot inside the domain."""
    if any(char.isspace() for char in email) or email.count("@") != 1:
        return False
    local, domain = email.split("@")
    return bool(local) and "." in domain and not (
        domain.startswith(".") or domain.endswith(".")
    )


def _register_error(message, name, email):
    """Re-render the form with an error, keeping name/email but never the password."""
    return render_template("register.html", error=message, name=name, email=email), 400


@app.route("/register", methods=["GET", "POST"])
def register():
    if _get_current_user():
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name:
        return _register_error("Name is required", name, email)
    if not _is_valid_email(email):
        return _register_error("Enter a valid email address", name, email)
    if len(password) < MIN_PASSWORD_LENGTH:
        return _register_error(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters", name, email
        )

    duplicate_error = "An account with this email already exists"
    if get_user_by_email(email):
        return _register_error(duplicate_error, name, email)
    try:
        create_user(name, email, password)
    except sqlite3.IntegrityError:
        return _register_error(duplicate_error, name, email)

    flash("Account created — please sign in")
    return redirect(url_for("login"))


def _login_error(message, email, status):
    """Re-render the form with an error, keeping the email but never the password."""
    return render_template("login.html", error=message, email=email), status


@app.route("/login", methods=["GET", "POST"])
def login():
    if _get_current_user():
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        return _login_error("Email and password are required", email, 400)

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return _login_error("Invalid email or password", email, 401)

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/logout", methods=["GET", "POST"])
def logout():
    # Only the navbar's Sign out button (POST) signs a user out; typing /logout
    # in the address bar (GET) sends a signed-in user back home.
    if _get_current_user():
        if request.method == "GET":
            return redirect(url_for("landing"))
        session.clear()
        flash("You have been signed out")
    return redirect(url_for("login"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


def _initials(name):
    """First letter of the first and last words of a name, uppercased."""
    words = name.split()
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[-1][0]).upper()


def _format_member_since(created_at):
    """'2026-09-18 10:30:00' -> 'Sep 2026'; falls back to the raw value."""
    try:
        return datetime.strptime(created_at[:10], "%Y-%m-%d").strftime("%b %Y")
    except (TypeError, ValueError):
        return created_at


# ------------------------------------------------------------------ #
# Profile date filter                                                 #
# ------------------------------------------------------------------ #

_PRESET_LABELS = {
    "this_month": "This Month",
    "last_3_months": "Last 3 Months",
    "last_6_months": "Last 6 Months",
    "all_time": "All Time",
}
_PRESET_ORDER = ("this_month", "last_3_months", "last_6_months", "all_time")


def _months_ago(today, months):
    """Return the date `months` calendar months before `today`, day clamped
    to the target month's length (so e.g. Mar 31 minus 1 month -> Feb 28/29)."""
    month_index = today.month - 1 - months
    year = today.year + month_index // 12
    month = month_index % 12 + 1
    day = min(today.day, monthrange(year, month)[1])
    return date(year, month, day)


def _preset_range(preset, today):
    """Return (date_from, date_to) ISO strings for a named preset, or (None,
    None) for "all_time" / an unknown preset name."""
    if preset == "this_month":
        return today.replace(day=1).isoformat(), today.isoformat()
    if preset == "last_3_months":
        return _months_ago(today, 3).isoformat(), today.isoformat()
    if preset == "last_6_months":
        return _months_ago(today, 6).isoformat(), today.isoformat()
    return None, None


def _parse_iso_date(value):
    """Parse a 'YYYY-MM-DD' string into a date, or None if missing/malformed."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_date_filter():
    """Read and validate date_from/date_to from the query string.

    Returns (date_from, date_to) as ISO strings when both are present and
    well-formed with date_from <= date_to. Otherwise returns (None, None) —
    an "All Time" fallback — flashing an error only when both dates parsed
    but were reversed.
    """
    raw_from = request.args.get("date_from", "").strip()
    raw_to = request.args.get("date_to", "").strip()

    parsed_from = _parse_iso_date(raw_from)
    parsed_to = _parse_iso_date(raw_to)

    if parsed_from is None or parsed_to is None:
        return None, None

    if parsed_from > parsed_to:
        flash("Start date must be before end date.")
        return None, None

    return raw_from, raw_to


def _active_preset(date_from, date_to, today):
    """Return the preset key matching (date_from, date_to), or None for a
    custom range."""
    if date_from is None and date_to is None:
        return "all_time"
    for preset in ("this_month", "last_3_months", "last_6_months"):
        if _preset_range(preset, today) == (date_from, date_to):
            return preset
    return None


@app.route("/profile")
def profile():
    user_row = _get_current_user()
    if user_row is None:
        return redirect(url_for("login"))

    user = {
        "name": user_row["name"],
        "email": user_row["email"],
        "initials": _initials(user_row["name"]),
        "member_since": _format_member_since(user_row["created_at"]),
    }
    user_id = user_row["id"]

    date_from, date_to = _parse_date_filter()
    today = date.today()
    active_preset = _active_preset(date_from, date_to, today)
    presets = [
        {
            "key": key,
            "label": _PRESET_LABELS[key],
            "date_from": _preset_range(key, today)[0],
            "date_to": _preset_range(key, today)[1],
            "active": key == active_preset,
        }
        for key in _PRESET_ORDER
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=get_expense_summary(user_id, start_date=date_from, end_date=date_to),
        transactions=get_recent_expenses(user_id, start_date=date_from, end_date=date_to),
        categories=get_category_breakdown(user_id, start_date=date_from, end_date=date_to),
        presets=presets,
        date_from=date_from,
        date_to=date_to,
        custom_active=active_preset is None and date_from is not None,
    )


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
