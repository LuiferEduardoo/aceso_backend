# Aceso Backend

Multi-user sports & health API: **Gym** (calendar, exercises, routines, flexible set tracking),
**Health** (watch data: HR, calories, steps, sleep, stress) and **Running** (training plans + Strava).

## Commit rules

- Use **Conventional Commits**, written in **English**, with a short subject
  (e.g. `feat(gym): add exercise sets`, `fix(health): handle empty sleep data`).
- **One commit per relevant change.** Never create large commits that mix unrelated things.
  Keep tests in the same commit as the code they test.
- Commits are authored **only by the user (LuiferEduardoo)**. Never add `Co-Authored-By`
  or any AI attribution/trailer to commit messages or PR descriptions.
- Never bypass git hooks (`--no-verify`).

## Stack

- Python 3.12+, managed with **uv**
- FastAPI, Pydantic v2, pydantic-settings
- PostgreSQL + SQLAlchemy 2.0 (async, `asyncpg`) + Alembic
- Auth: `pwdlib[argon2]` + `pyjwt`; third-party tokens encrypted at rest with Fernet (`cryptography`)
- External: `httpx` (Strava API), `garminconnect` (unofficial Garmin client)
- Tooling: Ruff (lint + format), pytest + pytest-asyncio

## Architecture (screaming + hexagonal)

```
src/aceso/
  main.py        # app factory, router includes, error handlers
  shared/        # config, db, security, storage port/adapter, integration credentials, errors
  identity/      # users, register/login/me, CurrentUserDep
  gym/           # exercises, routines, workout sessions (calendar), sets, intervals
  health/        # ingest + queries, Garmin adapter
  running/       # training plans, planned runs, activities, Strava
```

Each feature module has the same layers:

- `domain/` — entities (dataclasses), enums and ports (`Protocol`). **Must not import FastAPI,
  SQLAlchemy, httpx or any framework.**
- `application/` — use cases. Depend only on domain ports; unit-tested with in-memory fakes.
- `infrastructure/` — SQLAlchemy models + repositories, external clients/adapters.
- `api/` — FastAPI routers, Pydantic schemas and dependency wiring.

Rules:

- Every resource is scoped to the authenticated user (`user_id`); never return or mutate
  another user's data. Missing or foreign resources respond 404.
- FastAPI conventions: `Annotated` params and dependency type aliases (`SessionDep`,
  `CurrentUserDep`), return types on path operations, router-level `prefix`/`tags`,
  no `...` (Ellipsis) defaults, no `RootModel`.
- PostgreSQL conventions: `BIGINT GENERATED ALWAYS AS IDENTITY` PKs, `timestamptz`, `text`,
  explicit indexes on FK columns, `CHECK` constraints for enums/ranges, `ON DELETE` on every FK.
- Schema changes always ship with an Alembic migration (one per feature step).
- Blocking libraries (e.g. `garminconnect`) run in a threadpool, never directly in async code.

## Commands

```bash
uv sync                                   # install dependencies
cp .env.example .env                      # then fill secrets
docker compose up -d                      # Postgres (dev + test databases)
uv run alembic upgrade head               # apply migrations
uv run alembic revision --autogenerate -m "message"   # new migration
uv run fastapi dev                        # dev server -> http://127.0.0.1:8000/docs
uv run pytest                             # tests (needs the test database running)
uv run ruff check . && uv run ruff format --check .   # lint + format check
```
