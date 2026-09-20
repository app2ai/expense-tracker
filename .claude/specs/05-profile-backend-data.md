# Spec: Profile Backend Data

## Overview
Step 4 built the profile page UI using hardcoded Python dicts/lists in `app.py` (`PROFILE_STATS`, `PROFILE_TRANSACTIONS`, `PROFILE_CATEGORIES`). This step replaces that placeholder data with real queries against the `expenses` table, scoped to the logged-in user. The summary stats, recent transactions list, and category breakdown all become live, so a user who registers or is seeded sees their own numbers. All SQL lives in `database/db.py`; the `/profile` route only fetches data and renders the existing template.

## Depends on
- Step 1: Database setup (`users` and `expenses` tables, `seed_db()`)
- Step 2: Registration (new users start with zero expenses)
- Step 3: Login + Logout (`session["user_id"]`, `_get_current_user()`)
- Step 4: Profile page (`profile.html`, `profile.css`, user identity already real)

## Routes
No new routes. `GET /profile` (logged-in only) is modified to use database queries instead of hardcoded constants.

## Database changes
No database changes. The existing `users` and `expenses` tables are sufficient (verified against `database/db.py`: `expenses` has `user_id`, `amount`, `category`, `date`, `description`).

New query helper functions are added to `database/db.py` (see below); no schema changes.

### New helpers in `database/db.py`
Each takes `user_id`, opens its own connection via `get_db()`, uses parameterised queries, and closes the connection in a `finally` block (matching existing helpers).

- `get_expense_summary(user_id)` — returns `{"total_spent": float, "transaction_count": int, "top_category": str | None}`.
  - `total_spent` is `SUM(amount)` (0.0 when there are no expenses)
  - `transaction_count` is `COUNT(*)`
  - `top_category` is the category with the highest total spend (ties broken alphabetically for determinism); `None` when there are no expenses
- `get_recent_expenses(user_id, limit=10)` — returns a list of dicts `{"date", "description", "category", "amount"}` ordered by `date DESC, id DESC`, limited to `limit`. A `NULL` description is returned as an empty string.
- `get_category_breakdown(user_id)` — returns a list of dicts `{"name", "amount", "percent"}` ordered by amount descending (ties by name). `percent` is an integer; the percentages must sum to exactly 100 when there is at least one expense (use largest-remainder rounding). Returns an empty list when there are no expenses.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Handle the empty state for the stats row: when `stats.top_category` is `None`, show "—" instead of a badge (no `badge-none` class)
  - Show an empty-state message in the category breakdown when `categories` is empty (the transaction table already has one)
  - Otherwise the template contract (`user`, `stats`, `transactions`, `categories`) is unchanged

## Files to change
- `database/db.py` — add the three helper functions above
- `app.py` — import the helpers; remove `PROFILE_STATS`, `PROFILE_TRANSACTIONS`, `PROFILE_CATEGORIES` and the "replaced in Step 5" comment; call the helpers in `profile()` using `user_row["id"]`
- `templates/profile.html` — empty-state handling as described above
- `static/css/profile.css` — only if the category empty-state needs a style (reuse existing variables)
- `tests/test_profile.py` — update tests that assert on the old hardcoded values

## Files to create
- `tests/test_profile_data.py` — tests for the new db helpers and for `/profile` rendering real data

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never f-strings or string formatting in SQL
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No DB logic in route functions — all SQL lives in `database/db.py`
- Route function stays single-responsibility: fetch data, render template
- Every query must filter by `user_id` — one user must never see another user's expenses
- Amounts are INR only — no currency field or conversion logic
- Do not implement stub routes (add/edit/delete expense); do not touch the login/register flows
- No inline styles; category badges keep using the `badge-<category>` CSS classes
- Do not change the port (5001) or add pip packages

## Definition of done
- [ ] Logging in as the seeded demo user (`demo@spendly.com` / `demo123`) and opening `/profile` shows a total spent of ₹5,164.25 and 8 transactions
- [ ] The top category for the demo user is "Bills" (₹1,850.00), shown with a Bills badge
- [ ] The transaction table lists the demo user's expenses newest first, with correct date, description, category badge and ₹ amount
- [ ] The category breakdown lists each category with its ₹ total and a percentage; percentages sum to 100
- [ ] A newly registered user with no expenses sees ₹0.00, 0 transactions, "—" for top category, the "No transactions yet." message, and an empty-state message in the breakdown, with no errors (HTTP 200)
- [ ] Two different users each see only their own expenses on `/profile`
- [ ] `PROFILE_STATS`, `PROFILE_TRANSACTIONS` and `PROFILE_CATEGORIES` no longer exist in `app.py`
- [ ] No SQL appears in `app.py`; all queries are in `database/db.py` and use `?` placeholders
- [ ] `/profile` still redirects to `/login` when not signed in
- [ ] No hex colour values appear in `profile.html`
