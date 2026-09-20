# Spec: Login and Logout

## Overview
Make the existing `/login` page functional and replace the `/logout` placeholder. Today `GET /login` only renders a static form and `GET /logout` returns the raw string "Logout — coming in Step 3". This step adds the `POST /login` handler that verifies the submitted email and password against the `users` table (using werkzeug's `check_password_hash`), stores the user's id in the Flask session, and redirects to the landing page. `GET /logout` clears the session and redirects to the landing page. The shared navbar becomes session-aware (guests see "Sign in" / "Get started"; signed-in users see their name and "Sign out"). This is the second half of authentication and is required before any protected page (profile, expenses) can be built in later steps.

## Depends on
- Step 01 — Database Setup (`users` table, `get_db()`, seeded demo user `demo@spendly.com` / `demo123`)
- Step 02 — Registration (`get_user_by_email()`, `app.secret_key`, flash-message rendering in `login.html`, `.auth-success` style)

## Routes
- `GET /login` — render the sign-in form (already exists); if a user is already signed in, redirect to `GET /` — public
- `POST /login` — validate form input, verify credentials, start the session and redirect to `GET /` on success; re-render `login.html` with an error message and HTTP 400 on missing fields or HTTP 401 on bad credentials — public
- `GET /logout` — clear the session, flash "You have been signed out", redirect to `GET /login` — logged-in (a guest hitting it is simply redirected to `/login`, no error)
- `GET /register` — existing route; add one behaviour: if a user is already signed in, redirect to `GET /` — public

Both methods of `/login` are served by the single existing `login` view (`methods=["GET", "POST"]`). No other routes are added or changed. Stub routes (`/profile`, `/expenses/*`) must remain untouched — login redirects to the landing page, **not** `/profile`, because `/profile` is still a Step 4 placeholder.

## Database changes
No database changes. No schema changes and no new helpers are needed: `get_user_by_email(email)` (Step 02) already returns the full row including `password_hash`.

One new read helper is added to `database/db.py` so the navbar can show the signed-in user's name without SQL in `app.py`:
- `get_user_by_id(user_id)` — parameterised `SELECT` returning the `sqlite3.Row` or `None`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — change `action="/login"` to `action="{{ url_for('login') }}"`; repopulate the `email` input (never the password) with the submitted value after a failed submit.
  - `templates/base.html` — make the navbar session-aware using a `current_user` template variable: when `current_user` is set show the user's name and a "Sign out" link (`url_for('logout')`); otherwise show the existing "Sign in" / "Get started" links.

## Files to change
- `app.py` — import `session`, `abort` (if used) and `get_user_by_id`; extend the `login` view to handle POST; implement `logout`; redirect signed-in users away from `/login` and `/register`; add a `@app.context_processor` that exposes `current_user` (looked up via `get_user_by_id(session.get("user_id"))`, cleared from the session if the user no longer exists)
- `database/db.py` — add `get_user_by_id()`
- `templates/login.html` — see Templates
- `templates/base.html` — see Templates
- `static/css/style.css` — add small nav styles for the signed-in state (user name label + sign-out link), CSS variables only

## Files to create
- `tests/test_login_logout.py` — pytest tests for the login/logout flow (uses a temporary database, not `expense_tracker.db`; reuse the fixtures in `tests/conftest.py`)

## New dependencies
No new dependencies. (`flask`, `werkzeug`, `pytest`, `pytest-flask` are already in `requirements.txt`.)

## Validation rules
Applied server-side in the `login` view:
- `email` — required; stripped and lower-cased before lookup (`get_user_by_email` already normalises)
- `password` — required; not trimmed
- Missing email or password → error "Email and password are required", HTTP 400
- Unknown email **or** wrong password → the same generic error "Invalid email or password", HTTP 401 (never reveal which of the two was wrong)
- Error messages are passed to the template as `error` (one at a time)

## Session handling
- Store only `session["user_id"]` (an int) — never the password hash or other user data
- Call `session.clear()` before setting `user_id` on login to avoid session fixation
- `logout` calls `session.clear()`
- No "remember me", no `next` redirect parameter (avoids open-redirect risk at this stage)

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never f-strings or string formatting in SQL
- Passwords verified with werkzeug (`check_password_hash`); never log or echo the plain password
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; routes just read the form, call helpers, and redirect/render
- Use `url_for()` for every internal link and redirect — no hardcoded URLs
- Use `abort()` for HTTP errors where appropriate, not bare error strings
- Do not implement any stub route (`/profile`, `/expenses/*`) and do not change their placeholder responses
- Do not add a `SECRET_KEY` requirement that breaks the existing dev fallback
- Keep the app on port 5001; INR only — no currency fields
- Vanilla JS only (no JS is required for this step)

## Definition of done
- [ ] `GET /login` renders the form with no errors when signed out; the form's `action` is `/login` generated via `url_for('login')`
- [ ] Logging in as `demo@spendly.com` / `demo123` redirects (302) to `/` and the navbar shows "Demo User" and a "Sign out" link instead of "Sign in" / "Get started"
- [ ] Email matching is case-insensitive and whitespace-trimmed (`  Demo@Spendly.com ` logs in)
- [ ] A newly registered user (Step 02) can log in with the credentials they registered with
- [ ] A wrong password and an unknown email both re-render the form with the identical "Invalid email or password" message and status 401
- [ ] Submitting a blank email or blank password re-renders the form with "Email and password are required" and status 400 (server-side, e.g. via a direct POST)
- [ ] After a failed login the email field keeps its value; the password field is empty
- [ ] After login, visiting `/login` or `/register` redirects to `/`
- [ ] `GET /logout` while signed in clears the session, redirects to `/login`, shows "You have been signed out", and the navbar returns to "Sign in" / "Get started"
- [ ] `GET /logout` while signed out redirects to `/login` without error
- [ ] The session cookie contains only the user id (no password hash); a session whose user id no longer exists is treated as signed out
- [ ] `/logout` no longer returns the raw "Logout — coming in Step 3" string; `/profile` and `/expenses/*` placeholders are unchanged
- [ ] No SQL in `app.py`; all SQL is parameterised and in `database/db.py`
- [ ] `wenv\Scripts\pytest.exe tests/test_login_logout.py` passes and the existing `tests/test_registration.py` still passes
- [ ] App starts with `wenv\Scripts\python.exe app.py` on port 5001 without errors, and existing pages (`/`, `/register`, `/terms`, `/privacy`) still load
