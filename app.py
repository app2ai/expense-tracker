import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, url_for

from database.db import (  # noqa: F401
    create_user,
    get_db,
    get_user_by_email,
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


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    return "Logout — coming in Step 3"


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


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
