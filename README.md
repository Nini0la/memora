# Memora

Backend foundation for the Memora MVP.

## What is implemented now
- Auth endpoints: `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /me`
- Notes endpoints: `POST /notes` (paste), `POST /notes/upload` (text upload), `GET /notes/{id}`
- SQLite-backed persistence for users, sessions, and notes
- Integration tests for auth and note flows
- CI workflow that runs tests on push/PR

## Local development
```bash
uv run main.py
```

## Run tests
```bash
uv run --with pytest python -m pytest -q
```

## Test-first policy
See `status.md` for the mandatory tests-first execution policy and roadmap status.
