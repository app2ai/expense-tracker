# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

"Spendly" — a Flask-based expense tracker built as a step-by-step learning project. Routes and modules are scaffolded with comments like `# Students will write this file in Step 1 — Database Setup` and placeholder handlers that return strings like `"Logout — coming in Step 3"`. When asked to implement a feature, check whether the target file/route already has a "Step N" comment describing its intended scope before designing your own approach — the step comments are the spec.

## Environment & commands

A virtualenv already exists at `wenv/` (Windows). Use its interpreter/pip directly, or activate it first.

```powershell
# activate the venv
wenv\Scripts\Activate.ps1

# install dependencies
wenv\Scripts\pip.exe install -r requirements.txt

# run the app (listens on port 5001, debug mode on)
wenv\Scripts\python.exe app.py

# run tests
wenv\Scripts\pytest.exe

# run a single test
wenv\Scripts\pytest.exe path\to\test_file.py::test_name
```

There is no build/lint step configured (no linter config present). `requirements.txt` pins `flask`, `werkzeug`, `pytest`, `pytest-flask`.

## Architecture

spendly/
├── app.py              # All routes — single file, no blueprints
├── database/
│   └── db.py           # SQLite helpers: get_db(), init_db(), seed_db()
├── templates/
│   ├── base.html       # Shared layout — all templates must extend this
│   └── *.html          # One template per page
├── static/
│   ├── css/
│   │   ├── style.css       # Global styles
│   │   └── profile.css     # Profile-page-only styles
│   └── js/
│       └── main.js         # Vanilla JS only
└── requirements.txt


**Where things belong:**
- New routes → `app.py` only, no blueprints
- DB logic → `database/db.py` only, never inline in routes
- New pages → new `.html` file extending `base.html`
- Page-specific styles → new `.css` file, not inline `<style>` tags

- `app.py` — single-file Flask app; all routes are defined directly on `app` (no blueprints). Routes render templates via `render_template`; several are unimplemented placeholders awaiting future steps (logout, profile, add/edit/delete expense).
- `database/db.py` — intended to hold `get_db()` (SQLite connection with `row_factory` and foreign keys enabled), `init_db()` (creates tables with `CREATE TABLE IF NOT EXISTS`), and `seed_db()` (sample data for dev). Not yet implemented — currently just a spec comment.
- `templates/` — Jinja2 templates. `base.html` is the shared layout (nav + footer) that other templates extend via `{% block content %}`; page routes correspond 1:1 with template files (`landing.html`, `login.html`, `register.html`, `terms.html`, `privacy.html`).
- `static/css/style.css`, `static/js/main.js` — global stylesheet and script referenced from `base.html` via `url_for('static', ...)`.

No database file, migrations, or auth implementation exist yet — expect to build these from the `database/db.py` spec and the placeholder routes in `app.py` as steps progress.

---

## Code style

- Python: PEP 8, snake_case for all variables and functions
- Templates: Jinja2 with `url_for()` for every internal link — never hardcode URLs
- Route functions: one responsibility only — fetch data, render template, done
- DB queries: always use parameterized queries (`?` placeholders) — never f-strings in SQL
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`

---

## Tech constraints

- **Flask only** — no FastAPI, no Django, no other web frameworks
- **SQLite only** — no PostgreSQL, no SQLAlchemy ORM, no external DB
- **Vanilla JS only** — no React, no jQuery, no npm packages
- **No new pip packages** — work within `requirements.txt` as-is unless explicitly told otherwise
- Python 3.10+ assumed — f-strings and `match` statements are fine
- **INR only** — the app supports Indian Rupees exclusively; no currency field, selector, or conversion logic

---

## Subagent Policy
- Always use a builtin explore subagent for codebase exploration 
  before implementing any new feature
- Always use a subagent to verify test results 
  after any implementation
- When asked to plan, delegate codebase research 
  to a subagent before presenting the plan
- always use a builtin plan subagent in plan mode

---

## Implemented vs stub routes

| Route | Status |
|---|---|
| `GET /` | Implemented — renders `landing.html` |
| `GET /register` | Implemented — renders `register.html` |
| `GET /login` | Implemented — renders `login.html` |
| `GET /logout` | Stub — Step 3 |
| `GET /profile` | Implemented — Steps 4-5, renders `profile.html` with real user identity and per-user stats, recent transactions and category breakdown read from the database |
| `GET/POST /expenses/add` | Implemented — Step 7, logged-in form rendering `add_expense.html`; validates and inserts via `create_expense()`, then redirects to `/profile` |
| `GET /expenses/<id>/edit` | Stub — Step 8 |
| `GET /expenses/<id>/delete` | Stub — Step 9 |

**Do not implement a stub route unless the active task explicitly targets that step.**

---

## Warnings and things to avoid

- **Never use raw string returns for stub routes** once a step is implemented — always render a template
- **Never hardcode URLs** in templates — always use `url_for()`
- **Never put DB logic in route functions** — it belongs in `database/db.py`
- **Never install new packages** mid-feature without flagging it — keep `requirements.txt` in sync
- **Never use JS frameworks** — the frontend is intentionally vanilla
- **`database/db.py` is currently empty** — do not assume helpers exist until the step that implements them
- **FK enforcement is manual** — SQLite foreign keys are off by default; `get_db()` must run `PRAGMA foreign_keys = ON` on every connection
- The app runs on **port 5001**, not the Flask default 5000 — don't change this