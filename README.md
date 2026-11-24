# BudgetBoard

A personal budget dashboard: import a bank statement CSV, get transactions
auto-categorized by keyword rules, set monthly limits per category, and
see budget-vs-actual with over-spend flags. Built as a real Django + DRF
service — multi-user, JWT-authenticated, Dockerized, and tested.

## What this replaced

Before this, I was tracking spending the way most people do: a spreadsheet
I manually updated once a week, with categories I made up inconsistently
on the spot and no way to tell mid-month whether I was about to blow a
budget until the bank statement arrived.

BudgetBoard replaces the manual spreadsheet step with:

- **CSV import that tolerates real bank export formats** — different
  banks label columns differently, use different negative-amount
  conventions, and format currency inconsistently. The importer
  normalizes all of that.
- **Idempotent re-import.** Re-uploading the same statement doesn't
  create duplicate transactions.
- **Rule-based auto-categorization**, applying the longest/most-specific
  matching keyword rule.
- **Budget-vs-actual per category per month**, with explicit over-budget
  flags.

## Stack

- Django 5.2 + Django REST Framework
- JWT auth via `djangorestframework-simplejwt`
- PostgreSQL in production, SQLite for local dev (same codebase, switched
  via `DATABASE_URL`)
- Dockerized, with `docker-compose.yml` for local Postgres + web
- GitHub Actions CI: lint (flake8) + full test suite with coverage,
  against a real Postgres service container

## Architecture notes

- **Multi-user from the start.** Every queryset is scoped to
  `request.user` at the `ViewSet` level (`UserScopedModelViewSet`),
  covered by a test that fetches another user's transaction by ID and
  asserts a 404.
- **Import logic is a plain function, not baked into the view**
  (`budgets/importer.py`), so it's unit tested directly against CSV
  strings without needing an HTTP client.
- **Dashboard math is isolated the same way** (`budgets/dashboard.py`),
  including the December month-rollover edge case.

## Running locally

### With Docker

```bash
cp .env.example .env
docker compose up --build
```

### Without Docker

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

## Running tests

```bash
pytest --cov=accounts --cov=budgets --cov-report=term-missing
```

24 tests covering CSV parsing edge cases, auto-categorization rule
precedence, import idempotency, budget-vs-actual calculations, and
API-level authentication/permission isolation.

## API overview

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register/` | POST | Create an account |
| `/api/auth/token/` | POST | Obtain a JWT access/refresh pair |
| `/api/categories/` | GET/POST | List/create categories |
| `/api/category-rules/` | GET/POST | Keyword → category rules |
| `/api/transactions/` | GET/POST | List/create transactions |
| `/api/import/` | POST | Upload a CSV (`file` field) to bulk-import |
| `/api/budgets/` | GET/POST | Set a monthly limit per category |
| `/api/dashboard/` | GET | Budget-vs-actual for a month |

## What I'd change next

- Category rules currently require exact substring matches; fuzzy
  matching would reduce manual-rule overhead for new merchants.
- No recurring-transaction detection yet (flagging subscriptions) —
  the next iteration.