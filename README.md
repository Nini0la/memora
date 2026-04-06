# Memora

Backend foundation for the Memora MVP.

## What is implemented now
- Auth endpoints: `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /me`
- Notes endpoints:
  - `POST /notes` (paste)
  - `POST /notes/upload` with extraction for `text/plain`, `application/pdf`, and `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - `GET /notes/{id}`
- Structuring + preview endpoints:
  - `POST /notes/{id}/process`
  - `GET /notes/{id}/outline`
  - `GET /subtopics/{id}`
  - `GET /subtopics/{id}/preview`
  - `GET /subtopics/{id}/prompts`
- Recall + learning loop endpoints:
  - `POST /recall/attempts`
  - `GET /recall/attempts/{id}`
  - `POST /recall/attempts/{id}/evaluate`
  - `GET /subtopics/{id}/history`
  - `GET /subtopics/{id}/review-schedule`
  - `GET /subtopics/{id}/mastery`
- SQLite-backed persistence for users, sessions, notes, subtopics, prompts, attempts, schedules, and mastery status
- Integration tests for auth, notes, structuring, preview mode, recall evaluation, and learning loop behavior
- CI workflow that runs tests on push/PR

## Local development
```bash
uv run main.py
```

## Run tests
```bash
uv run --group dev python -m pytest -q
```

## Test-first policy
See `status.md` for the mandatory tests-first execution policy and roadmap status.
