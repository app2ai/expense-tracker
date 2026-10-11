# Spec: Delete Expenses

## Overview
Step 9 replaces the `GET /expenses/<id>/delete` placeholder (which currently
returns the raw string "Delete expense — coming in Step 9") with a safe,
logged-in-only way for a user to remove one of their own expenses. Each row in
the profile page's "Recent transactions" table gets a "Delete" link next to the
existing "Edit" link. The link opens a confirmation page showing the expense's
date, description, category and amount (INR). Nothing is deleted on `GET`. The
expense is only deleted when the user submits the confirmation form (`POST`),
which follows the same rule as the navbar's Sign out button: a state-changing
action never runs from a plain link, prefetch or typed URL. After deleting, the
user is redirected to `/profile`, where the stats, recent transactions and
category breakdown no longer include the expense. This completes CRUD for
expenses and reuses the ownership pattern from Step 8: a user can only see or
delete expenses that belong to them.

## Depends on
- Step 1: Database setup — `expenses` table, `get_db()`
- Step 3: Login and Logout — `session["user_id"]`, `_get_current_user()`, and
  the POST-only pattern for state-changing actions
- Steps 4–6: Profile page — recent transactions table with the Actions column
  (the entry point and redirect target)
- Step 7: Add Expense — `add_expense.css` shared form/card styles
- Step 8: Edit Expense — `get_expense_by_id(expense_id, user_id)` and the
  owner-only / `abort(404)` pattern

## Routes
- `GET /expenses/<int:id>/delete` — render a confirmation page showing the
  expense's details with a "Delete expense" submit button and a "Cancel" link
  — logged-in (owner only)
- `POST /expenses/<int:id>/delete` — delete the expense, flash a success
  message and redirect to `/profile` — logged-in (owner only)

Both methods live on the existing `delete_expense(id)` view (change its
decorator to `methods=["GET", "POST"]`). Logged-out users are redirected to
`/login`. An expense id that does not exist **or** belongs to another user
returns `abort(404)` on both GET and POST (never 403, so the route doesn't
reveal that another user's id exists).

## Database changes
No schema changes.

Add one helper to `database/db.py`:
- `delete_expense(expense_id, user_id)` — parameterised
  `DELETE FROM expenses WHERE id = ? AND user_id = ?` inside a `with conn:`
  transaction. It returns `True` if a row was deleted (`cursor.rowcount == 1`),
  otherwise `False`. Same connection/`try`/`finally` shape as `update_expense`.

Reuse the existing `get_expense_by_id(expense_id, user_id)` to load the
expense for the confirmation page and for the ownership check.

## Templates
- **Create:** `templates/delete_expense.html` — extends `base.html` and uses
  the same card layout and classes as `edit_expense.html`. It contains:
  - title/heading "Delete expense"
  - a short warning: "This will permanently delete this expense. This can't be
    undone."
  - a read-only summary of the expense: date, description (or "No
    description" when empty), category badge, and amount formatted with the
    existing `inr()` helper
  - a form with `method="POST"` and
    `action="{{ url_for('delete_expense', id=expense.id) }}"`, a submit button
    labelled "Delete expense", and no input fields
  - a "Cancel" link back to `url_for('profile')`
  - `add_expense.css` linked through `{% block head %}`. Any extra styling
    (the danger button, the summary list) goes in `static/css/add_expense.css`
    using CSS variables.
- **Modify:** `templates/profile.html` — in the Actions cell of each Recent
  transactions row, add a "Delete" link (`url_for('delete_expense', id=tx.id)`,
  class `tx-delete-link`, `aria-label="Delete expense from {{ tx.date }}"`)
  next to the existing Edit link. Its styling goes in `static/css/profile.css`.

## Files to change
- `app.py`
  - Import `delete_expense` from `database.db`. The view is also named
    `delete_expense`, so import the helper under an alias such as
    `delete_expense as db_delete_expense` to avoid the name clash. Keep
    `url_for('delete_expense', ...)` as the endpoint name.
  - Replace the `delete_expense(id)` placeholder with the GET/POST handler
- `database/db.py` — add `delete_expense(expense_id, user_id)`
- `templates/profile.html` — Delete link in the Actions column
- `static/css/profile.css` — `.tx-delete-link` style
- `static/css/add_expense.css` — danger button / summary styles for the
  confirmation page, only if the existing styles aren't enough
- `CLAUDE.md` — mark `GET/POST /expenses/<id>/delete` as implemented in the
  routes table

## Files to create
- `templates/delete_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs. Use raw `sqlite3` through `get_db()` only.
- Parameterised queries only: `?` placeholders, never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables. Never hardcode hex values.
- All templates extend `base.html`
- No inline `<style>` tags or `style=""` attributes
- DB logic lives only in `database/db.py`. The route only loads the expense,
  renders the confirmation or calls the delete helper, then redirects.
- **GET never deletes.** Deletion happens only on `POST`.
- Ownership is enforced in SQL: the read and the delete both filter on `id`
  and `user_id`. `user_id` comes from the session (`_get_current_user()`),
  **never** from the form or URL.
- Missing or not-owned expense → `abort(404)` on both GET and POST. If the
  delete helper returns `False` (for example, the row was removed between
  load and delete), also `abort(404)`.
- On success: `flash("Expense deleted", "success")`, then
  `redirect(url_for("profile"))` (Post/Redirect/Get)
- No JavaScript `confirm()` dialogs. The confirmation page is the
  confirmation, and the feature must work with JS disabled.
- INR only: no currency field or selector
- All links and form actions via `url_for()`
- Don't change the add or edit expense behaviour

## Definition of done
- [ ] Visiting `/expenses/<id>/delete` while logged out redirects to `/login`
- [ ] Each row in the profile's Recent transactions table has a "Delete" link
      next to "Edit" that opens `/expenses/<that id>/delete`
- [ ] The confirmation page shows the expense's date, description, category
      and ₹ amount, plus "Delete expense" and "Cancel" controls
- [ ] Loading the confirmation page (GET) does **not** delete the expense.
      Going back to `/profile` still shows it.
- [ ] Clicking "Delete expense" redirects to `/profile` and shows "Expense
      deleted". The row is gone, the transaction count drops by 1, and total
      spent and the category breakdown update to match.
- [ ] Deleting the only expense in a category removes that category from the
      breakdown
- [ ] Deleting a user's last expense shows the "No transactions yet." empty
      state and zeroed stats
- [ ] Clicking "Cancel" returns to `/profile` with the expense unchanged
- [ ] `GET` or `POST` to `/expenses/99999/delete` (non-existent id) returns 404
- [ ] User B visiting or POSTing to `/expenses/<user A's expense id>/delete`
      gets 404, and user A's expense is still in the database
- [ ] POSTing to an already-deleted expense's delete URL returns 404
- [ ] Add expense and edit expense still work as before
