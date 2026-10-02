# Spec: Edit Expense

## Overview
Step 8 replaces the `GET /expenses/<id>/edit` placeholder (which currently
returns the raw string "Edit expense — coming in Step 8") with a real,
logged-in-only form that lets a user correct one of their own expenses. Each
row in the profile page's "Recent transactions" table gets an "Edit" link that
opens the form pre-filled with that expense's amount (INR only), category, date
and description. On a valid `POST` the row is updated in the `expenses` table
and the user is redirected back to `/profile`, where the stats, recent
transactions and category breakdown reflect the change. The step reuses the
form layout and validation rules built for Add Expense in Step 7, and adds the
first ownership check on a per-row resource: a user can only view or change
expenses that belong to them.

## Depends on
- Step 1: Database setup — `expenses` table, `get_db()`, `CATEGORIES`
- Step 3: Login and Logout — `session["user_id"]` and `_get_current_user()`
- Steps 4–6: Profile page — recent transactions table and date filter (the
  entry point and redirect target)
- Step 7: Add Expense — `add_expense.html` form layout, `add_expense.css`,
  `_parse_amount()`, `_parse_iso_date()`, `MAX_DESCRIPTION_LENGTH`

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the
  expense's current values — logged-in (owner only)
- `POST /expenses/<int:id>/edit` — validate the form, update the expense,
  flash a success message and redirect to `/profile`; on validation failure
  re-render the form with an error and the submitted values, status 400 —
  logged-in (owner only)

Both methods live on the existing `edit_expense(id)` view (change its decorator
to `methods=["GET", "POST"]`). Logged-out users are redirected to `/login`.
An expense id that does not exist **or** belongs to another user returns
`abort(404)` (never 403 — do not reveal that another user's id exists).

## Database changes
No schema changes. The existing `expenses` table already covers every field.

Add / change helpers in `database/db.py`:
- `get_expense_by_id(expense_id, user_id)` — return the expense row
  (`id`, `amount`, `category`, `date`, `description` as `''` when NULL) only if
  it belongs to `user_id`; otherwise `None`. Single parameterised query with
  `WHERE id = ? AND user_id = ?`.
- `update_expense(expense_id, user_id, amount, category, expense_date, description)`
  — parameterised `UPDATE ... WHERE id = ? AND user_id = ?`; stores a
  blank/whitespace description as `NULL` (same rule as `create_expense`);
  returns `True` if a row was updated (`cursor.rowcount == 1`), else `False`.
- `get_recent_expenses(...)` — also select and return `id` in each dict so the
  profile template can build per-row edit links. No other behaviour changes.

## Templates
- **Create:** `templates/edit_expense.html` — extends `base.html`; same
  structure and classes as `add_expense.html` (amount, category select rendered
  from `categories`, date, optional description, error block), with:
  - title/heading "Edit expense"
  - form `POST`s to `url_for('edit_expense', id=expense_id)`
  - submit button labelled "Save changes"
  - "Cancel" link back to `url_for('profile')`
  - links `add_expense.css` via `{% block head %}` (shared form styles — no new
    CSS file needed)
- **Modify:** `templates/profile.html` — add an "Actions" column to the
  Recent transactions table with an "Edit" link per row
  (`url_for('edit_expense', id=tx.id)`); update the empty-state row's
  `colspan` from 4 to 5. Any new styling for the link goes in
  `static/css/profile.css`.

## Files to change
- `app.py`
  - Import `get_expense_by_id` and `update_expense` from `database.db`
  - Replace the `edit_expense(id)` placeholder with the GET/POST handler
  - Add `_edit_expense_error(message, form, expense_id)` helper (mirroring
    `_add_expense_error`) that re-renders `edit_expense.html` with status 400
  - Reuse `_parse_amount`, `_parse_iso_date`, `CATEGORIES`,
    `MAX_DESCRIPTION_LENGTH` — do not duplicate validation logic
- `database/db.py` — add `get_expense_by_id`, `update_expense`; return `id`
  from `get_recent_expenses`
- `templates/profile.html` — Actions column with Edit link
- `static/css/profile.css` — style for the Edit link (if needed)
- `CLAUDE.md` — mark `GET/POST /expenses/<id>/edit` as implemented in the
  routes table

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` through `get_db()` only
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline `<style>` tags or `style=""` attributes
- DB logic lives only in `database/db.py`; the route only fetches, validates,
  calls `update_expense`, and redirects/renders
- Ownership enforced in SQL: every read and update of an expense filters on
  both `id` and `user_id`, where `user_id` comes from the session
  (`_get_current_user()`), **never** from the form or URL
- Missing or not-owned expense → `abort(404)` on both GET and POST
- INR only — no currency field or selector
- Server-side validation identical to Step 7:
  - `amount` required, numeric, finite, `> 0`, rounded to 2 dp. Error:
    "Enter an amount greater than 0"
  - `category` must be one of `CATEGORIES`. Error: "Choose a valid category"
  - `date` required, valid `YYYY-MM-DD`. Error: "Enter a valid date"
  - `description` optional, stripped, max 200 characters. Error:
    "Description must be 200 characters or fewer"
- On success: `flash("Expense updated", "success")` then
  `redirect(url_for("profile"))` (Post/Redirect/Get)
- All links and form actions via `url_for()`
- Do not touch the delete (Step 9) placeholder route

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Each row in the profile's Recent transactions table has an "Edit" link
      that opens `/expenses/<that id>/edit`
- [ ] The edit form shows the expense's current amount, category, date and
      description pre-filled, with all seven categories in the dropdown
- [ ] Changing the amount/category/date/description and saving redirects to
      `/profile`, shows "Expense updated", and the row, total spent and
      category breakdown reflect the new values
- [ ] Saving does not create a new row — transaction count is unchanged
- [ ] Clearing the description and saving succeeds; the row shows an empty
      description
- [ ] Submitting amount `0`, `-5`, `abc` or blank re-renders the form with an
      error (HTTP 400) and the expense is unchanged in the database
- [ ] Submitting a tampered category, or a blank/malformed date, re-renders
      with an error (HTTP 400) and the expense is unchanged
- [ ] A description longer than 200 characters is rejected with an error
- [ ] After a validation error, the submitted values remain in the form
- [ ] `GET` or `POST` to `/expenses/99999/edit` (non-existent id) returns 404
- [ ] User B visiting or POSTing to `/expenses/<user A's expense id>/edit`
      gets 404 and user A's expense is unchanged
- [ ] Moving an expense's date outside the active profile date filter removes
      it from that filtered view
- [ ] The Cancel link returns to `/profile` without changing anything
- [ ] `/expenses/<id>/delete` still returns its Step 9 placeholder
