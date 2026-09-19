# Spec: Registration

## Overview
Make the existing `/register` page functional. Today `GET /register` only renders a static form; this step adds the `POST /register` handler that validates the submitted name, email and password, hashes the password with werkzeug, inserts a new row into the `users` table, and redirects the new user to the login page with a success message. It is the first half of authentication and must exist before login/logout (Step 3) can work, since there is currently no way to create a user other than the seeded demo account.

## Depends on
- Step 01 — Database Setup (`users` table, `get_db()`, `init_db()` are already implemented in `database/db.py`)

## Routes
- `GET /register` — render the registration form (already exists; unchanged behaviour) — public
- `POST /register` — validate form input, create the user, redirect to `GET /login` on success; re-render `register.html` with an error message and HTTP 400 on validation failure — public

Both methods are served by the single existing `register` view (`methods=["GET", "POST"]`). No other routes are added or changed. Stub routes (`/logout`, `/profile`, `/expenses/*`) must remain untouched.

## Database changes
No schema changes. The `users` table already has `name`, `email` (UNIQUE, NOT NULL), `password_hash` and `created_at`.

New helpers in `database/db.py` (DB logic must not live in the route):
- `create_user(name, email, password)` — hashes the password with `generate_password_hash`, inserts the row with a parameterised query, returns the new user id. Raises `sqlite3.IntegrityError` if the email already exists (the UNIQUE constraint is the source of truth for duplicates).
- `get_user_by_email(email)` — returns the matching `sqlite3.Row` or `None`. Used for the friendly duplicate-email pre-check and reused by Step 3 (login).

## Templates
- **Create:** none
- **Modify:**
  - `templates/register.html` — change `action="/register"` to `action="{{ url_for('register') }}"`; repopulate the `name` and `email` inputs (never the password) with the submitted values after a failed submit; set `minlength="8"` on the password input to match the server rule.
  - `templates/login.html` — render any flashed messages (success banner "Account created — please sign in") above the form, using the same card layout as the existing `auth-error` block.

## Files to change
- `app.py` — import `request`, `redirect`, `url_for`, `flash`; set `app.secret_key` (read from the `SECRET_KEY` environment variable, falling back to a clearly-named dev-only default); extend the `register` view to handle POST
- `database/db.py` — add `create_user()` and `get_user_by_email()`
- `templates/register.html` — see Templates
- `templates/login.html` — see Templates
- `static/css/style.css` — add an `.auth-success` style alongside the existing `.auth-error` rule, using CSS variables only (`--accent`, `--accent-light`)

## Files to create
- `tests/test_registration.py` — pytest tests for the registration flow (uses a temporary database, not `expense_tracker.db`)

## New dependencies
No new dependencies. (`flask`, `werkzeug`, `pytest`, `pytest-flask` are already in `requirements.txt`.)

## Validation rules
Applied server-side in the `register` view (client-side `required`/`minlength` are a convenience only):
- `name` — required after stripping whitespace
- `email` — required, stripped and lower-cased before storing/lookup; must contain an `@` with non-empty text on both sides and a `.` in the domain part (simple format check, no new packages)
- `password` — required, minimum 8 characters (matches the placeholder text "Min. 8 characters"); passwords are not trimmed
- Email already registered → error "An account with this email already exists"
- Error messages are passed to the template as `error` (one message at a time) and re-rendered with status 400

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings or string formatting in SQL
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log the plain password
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route just reads the form, calls helpers, and redirects/renders
- Use `url_for()` for every internal link and redirect — no hardcoded URLs
- Catch `sqlite3.IntegrityError` from `create_user()` to handle a race on the UNIQUE email constraint; do not rely solely on the pre-check
- Do not log the user in after registering — session handling belongs to Step 3; redirect to `login` instead
- Do not implement any stub route (`/logout`, `/profile`, `/expenses/*`)
- Keep the app on port 5001; INR only — no currency fields
- Vanilla JS only (no JS is required for this step)

## Definition of done
- [ ] `GET /register` still renders the form with no errors
- [ ] The form's `action` is generated with `url_for('register')` (view page source: `/register`)
- [ ] Submitting valid name, email and an 8+ character password creates a row in `users` and redirects (302) to `/login`
- [ ] `/login` then shows the "Account created — please sign in" message
- [ ] The stored `password_hash` is a werkzeug hash (not the plain password) and `check_password_hash` accepts the original password
- [ ] Submitting an email that already exists (including `demo@spendly.com` and a different-case variant like `Demo@Spendly.com`) re-renders the form with the duplicate-email error and status 400, and does not create a second row
- [ ] Submitting with a blank name, an invalid email, or a password shorter than 8 characters re-renders the form with a specific error and status 400, and creates no row
- [ ] After a failed submit the name and email fields keep their values; the password field is empty
- [ ] Email is stored lower-cased and trimmed
- [ ] No SQL in `app.py`; all SQL is parameterised and in `database/db.py`
- [ ] `wenv\Scripts\pytest.exe tests/test_registration.py` passes
- [ ] App starts with `wenv\Scripts\python.exe app.py` on port 5001 without errors, and existing pages (`/`, `/login`, `/terms`, `/privacy`) still load
