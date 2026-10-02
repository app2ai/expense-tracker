# Spec: Add Expense

## Overview
Step 7 replaces the `GET /expenses/add` placeholder (which currently returns the
raw string "Add expense — coming in Step 7") with a real, logged-in-only form
that lets a user record a new expense. The form captures amount (INR only),
category, date and an optional description; on a valid `POST` the expense is
inserted into the `expenses` table for the signed-in user and they are
redirected to `/profile`, where the new row immediately shows up in the stats,
recent transactions and category breakdown built in Steps 5–6. This is the
first step where users create their own data instead of relying on seed rows,
and it sets up the form/validation patterns that Step 8 (edit) will reuse.

## Depends on
- Step 1: Database setup — `expenses` table, `get_db()`, `CATEGORIES` tuple in
  `database/db.py`
- Step 2: Registration — users exist
- Step 3: Login and Logout — `session["user_id"]` and `_get_current_user()`
- Steps 4–6: Profile page — the redirect target that displays the new expense

## Routes
- `GET /expenses/add` — render the empty add-expense form (date pre-filled
  with today) — logged-in
- `POST /expenses/add` — validate the form, insert the expense, flash a success
  message and redirect to `/profile`; on validation failure re-render the form
  with an error and the submitted values, status 400 — logged-in

Both methods live on the existing `add_expense()` view (change its decorator to
`methods=["GET", "POST"]`). Logged-out users are redirected to `/login`.

## Database changes
No database changes. The existing `expenses` table (`user_id`, `amount`,
`category`, `date`, `description`, `created_at`) already covers every field.

Add one helper to `database/db.py`:
- `create_expense(user_id, amount, category, expense_date, description)` —
  inserts a row with a parameterised `INSERT`, stores an empty/whitespace
  description as `NULL`, and returns the new row id.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; a form that
  `POST`s to `url_for('add_expense')` with:
  - `amount` — `<input type="number" step="0.01" min="0.01">`, labelled with ₹
  - `category` — `<select>` whose options are rendered from the `categories`
    list passed by the route (never hardcoded in the template)
  - `date` — `<input type="date">`, defaults to today
  - `description` — optional text input
  - a submit button and a "Cancel" link back to `url_for('profile')`
  - an error block showing the validation message when present
- **Modify:** `templates/profile.html` — add an "Add expense" button/link
  (via `url_for('add_expense')`) near the top of the page so the form is
  reachable from the UI. The existing flash-message block already renders the
  success message.

## Files to change
- `app.py`
  - Import `create_expense` and `CATEGORIES` from `database.db`
  - Replace the `add_expense()` placeholder with the GET/POST handler
  - Add a small `_add_expense_error(message, form)` helper (mirroring
    `_register_error`) that re-renders the form with the error and submitted
    values, status 400
- `database/db.py` — add `create_expense(...)`
- `templates/profile.html` — add the "Add expense" link
- `CLAUDE.md` — mark `GET /expenses/add` as implemented in the routes table

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` — form-page styles, linked only from
  `add_expense.html` (via a `{% block head %}`-style extension point in
  `base.html` if one exists, otherwise follow however `profile.css` is loaded)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` through `get_db()` only
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline `<style>` tags or `style=""` attributes
- DB logic lives only in `database/db.py`; the route only parses, validates,
  calls `create_expense`, and redirects/renders
- `user_id` comes from the session (`_get_current_user()`), **never** from the
  form
- INR only — no currency field or selector
- Server-side validation (HTML attributes are not sufficient):
  - `amount` required, parses as a number, finite, `> 0`; round to 2 dp before
    storing. Error: "Enter an amount greater than 0"
  - `category` must be one of `CATEGORIES`. Error: "Choose a valid category"
  - `date` required, valid `YYYY-MM-DD` (reuse `_parse_iso_date`). Error:
    "Enter a valid date"
  - `description` optional, stripped, max 200 characters. Error:
    "Description must be 200 characters or fewer"
- On success: `flash("Expense added")` then
  `redirect(url_for("profile"))` (Post/Redirect/Get)
- All links and form actions via `url_for()`
- Do not touch the edit (Step 8) or delete (Step 9) placeholder routes

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows the form with all seven
      categories in the dropdown and today's date pre-filled
- [ ] The profile page has an "Add expense" link that opens the form
- [ ] Submitting a valid expense (e.g. ₹250.50, Food, today, "Lunch")
      redirects to `/profile`, shows "Expense added", and the new row appears
      in recent transactions with total spent and category breakdown updated
- [ ] Submitting with no description succeeds and the transaction shows an
      empty description
- [ ] Submitting amount `0`, `-5`, `abc` or blank re-renders the form with an
      error (HTTP 400) and no row is inserted
- [ ] Submitting a category not in the list (tampered form) re-renders with an
      error and no row is inserted
- [ ] Submitting a blank or malformed date re-renders with an error and no row
      is inserted
- [ ] A description longer than 200 characters is rejected with an error
- [ ] After a validation error, previously entered values remain in the form
- [ ] An expense added by one user never appears on another user's profile
- [ ] A backdated expense shows up only under date filters that include its date
- [ ] The Cancel link returns to `/profile` without creating anything
