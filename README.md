# Memora

Memora MVP in progress. Backend core learning loop is implemented, and the frontend now has an initial Auth + Notes vertical slice.

## Backend status (implemented)
- Auth: `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /me`
- Notes: `POST /notes`, `POST /notes/upload`, `GET /notes/{id}`
- Structuring: `POST /notes/{id}/process`, `GET /notes/{id}/outline`, `GET /subtopics/{id}`, `GET /subtopics/{id}/preview`, `GET /subtopics/{id}/prompts`
- Recall: `POST /recall/attempts`, `GET /recall/attempts/{id}`, `POST /recall/attempts/{id}/evaluate`
- Learning loop: `GET /subtopics/{id}/history`, `GET /subtopics/{id}/review-schedule`, `GET /subtopics/{id}/mastery`

## Frontend status (implemented)
`frontend/` contains a React + TypeScript app with:
- Auth screen (sign up/login toggle)
- Notes workspace (paste note form)
- API integration to backend auth + `POST /notes`
- Session persistence in `localStorage`
- Vitest + Testing Library tests for core flows

## Local development
Backend:
```bash
uv run main.py
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Run tests
Backend:
```bash
uv run --group dev python -m pytest -q
```

Frontend:
```bash
cd frontend
npm run test -- --run
```

## Test-first policy
See `status.md` for the mandatory tests-first execution policy and roadmap snapshot.
