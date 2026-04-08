# Memora MVP Implementation Status

Last Updated: 2026-04-07

## Execution Policy (Mandatory)
- Test-first development is required for all MVP features.
- For every story, write failing tests first, then implement code to pass.
- No feature is marked complete unless its automated tests are green in CI.
- PR review gate: no untested endpoint, scheduler rule, or evaluator logic merges.

## Current Snapshot
- In Progress: Sprint 5 kickoff (dashboard + reminders pending) and Frontend Slice 2 planning.
- Completed Today:
  - Added integration tests for auth flows and note input/upload edge cases.
  - Implemented backend API scaffolding (FastAPI, DB models, session auth).
  - Implemented and verified endpoints:
    - `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /me`
    - `POST /notes`, `POST /notes/upload` (text/plain + PDF + DOCX), `GET /notes/{id}`
    - `POST /notes/{id}/process`, `GET /notes/{id}/outline`, `GET /subtopics/{id}`
    - `GET /subtopics/{id}/preview`, `GET /subtopics/{id}/prompts`
    - `POST /recall/attempts`, `GET /recall/attempts/{id}`, `POST /recall/attempts/{id}/evaluate`
    - `GET /subtopics/{id}/review-schedule`, `GET /subtopics/{id}/history`, `GET /subtopics/{id}/mastery`
  - Implemented upload extraction with corruption handling for:
    - invalid UTF-8 text uploads
    - malformed PDF uploads
    - malformed DOCX uploads
  - Implemented deterministic evaluation scoring (`score`, `level`, `missing_concepts`, `feedback`).
  - Implemented review schedule generation and accelerated schedule for low performance.
  - Implemented mastery threshold evaluation (`Level >= 4` on different days).
  - Added React + TypeScript frontend scaffold in `frontend/`.
  - Implemented frontend Auth + Notes slice:
    - signup/login toggle UI
    - notes workspace paste form
    - backend integration for auth and `POST /notes`
    - session persistence via `localStorage`
  - Added frontend tests (Vitest + Testing Library) for:
    - unauthenticated auth form rendering
    - login flow transition into notes workspace
    - paste note request shape with bearer token
  - Expanded CI workflow to run both backend and frontend test jobs.
  - Test status: backend `30 passed`; frontend `3 passed` on 2026-04-07.
- Next Immediate Gate:
  - Add failing tests for Sprint 5 dashboard and reminders:
    - `GET /dashboard`
    - `GET /reviews/due`
    - `GET /notifications`
  - Add Frontend Slice 2 (Structuring + Preview):
    - processed outline page
    - subtopic preview with “Start Recall Training” CTA
    - route wiring and API integration

## Frontend Workstream (Vertical Slices)
- Slice 1 (Done): Auth + Notes input UI wired to backend.
- Slice 2 (Next): Outline + preview UI for processed notes.
- Slice 3: Recall answer submission + evaluation result UI.
- Slice 4: Dashboard + due reviews + notification panel.
- Slice 5: Responsive polish, E2E flows, accessibility pass.

## Implementation Roadmap (8 Weeks)

| Phase | Dates | Build Scope | Exit Criteria |
|---|---|---|---|
| 0. Foundation | Apr 6-Apr 10 | Repo setup, environments, CI, migrations, auth scaffolding, logging/error tracking, base UI shell | Dev/staging deploys succeed, CI green, app boots end-to-end |
| 1. Accounts + Notes | Apr 13-Apr 24 | Auth/profile, paste input, file upload + extraction pipeline, note persistence, processing states/errors | User can register/login and upload/paste notes that are stored correctly |
| 2. Structuring + Preview | Apr 27-May 8 | AI structuring, subtopics/key concepts/summaries/prompts, subtopic preview + CTA | Processed notes show structured outline and per-subtopic preview |
| 3. Recall + Evaluation | May 11-May 22 | Recall session UI, attempt submission/storage, AI scoring + levels + feedback | Every submitted attempt returns score/level/missing concepts and is saved |
| 4. Learning Loop | May 25-Jun 5 | Attempt history, spaced repetition scheduler, mastery threshold engine + badge | Review dates generated; mastery status updates when rule is met |
| 5. Dashboard + Reminders | Jun 8-Jun 12 | Progress dashboard metrics, due reviews list, in-app reminder center with deep links | Dashboard updates after attempts and due reviews are actionable |
| 6. Hardening + Beta | Jun 15-Jun 19 | QA/regression, analytics, rate limits, AI fallback/retries, launch checklist | Release candidate with no P0/P1 defects |

## Ticket-Level Plan

### Sprint 1 (Apr 6-Apr 17): Foundation + Core Account + Note Input

#### Epic A: Platform Foundations
- Story A1: Initialize environment config (`dev`, `staging`, `prod`) and secret management.
- Story A2: Add CI pipeline for lint, typecheck, tests, and build.
- Story A3: Add DB migration tooling and baseline schema bootstrap.
- Story A4: Add centralized error handling + request logging.

#### Epic B: Authentication and Profiles (PRD Feature 1)
- Story B1: Implement email/password signup.
- Story B2: Implement login/logout and session persistence.
- Story B3: Create profile fields: `name` (optional), `study_goal` (optional), `preferred_recall_mode` default `typing`.
- Story B4: Add auth-guarded dashboard shell.

#### Epic C: Note Upload/Input (PRD Feature 2)
- Story C1: Paste-text note input flow and validation.
- Story C2: File upload endpoint with MIME/type validation.
- Story C3: Text extraction for supported files with user-facing processing state.
- Story C4: Error handling for empty/corrupted/unsupported files and long-note warning.

#### Engineering Tasks
- Data model: `users`, `notes` tables.
- API: `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /me`, `POST /notes`, `POST /notes/upload`, `GET /notes/:id`.
- Tests: auth integration tests, upload validation tests.

### Sprint 2 (Apr 20-May 1): Structuring + Preview

#### Epic D: AI Structuring Engine (PRD Feature 3)
- Story D1: Queue processing job after note creation.
- Story D2: Generate topic title, subtopics (target 5-15), key concepts, optional summary.
- Story D3: Generate recall prompts per subtopic.
- Story D4: Persist structured outputs and status transitions.

#### Epic E: Preview Mode (PRD Feature 4)
- Story E1: Build subtopic preview page with headings, key concepts, summary, prompts preview.
- Story E2: Add `Start Recall Training` CTA and routing.

#### Engineering Tasks
- Data model: `subtopics`, `recall_prompts`.
- API: `POST /notes/:id/process`, `GET /notes/:id/outline`, `GET /subtopics/:id`, `GET /subtopics/:id/preview`.
- Tests: schema validation for AI output, outline rendering tests.

### Sprint 3 (May 4-May 15): Recall Session + Evaluation Core

#### Epic F: Recall Training Session (PRD Feature 5)
- Story F1: Recall prompt UI + answer input + submit flow.
- Story F2: Persist recall attempts with timestamps.
- Story F3: Optional timer support behind a feature flag.

#### Epic G: Evaluation Engine (PRD Feature 6)
- Story G1: Build scoring rubric service (accuracy, completeness, structure, terminology, exam readiness).
- Story G2: Return `score (0-100)`, `level (0-5)`, missing concepts, feedback.
- Story G3: Map output to mastery level labels.
- Story G4: Add fallback path for evaluator timeout/failure.

#### Engineering Tasks
- Data model: `recall_attempts`.
- API: `POST /recall/attempts`, `GET /recall/attempts/:id`, `POST /recall/attempts/:id/evaluate`.
- Tests: scorer contract tests, level mapping tests, failure mode tests.

### Sprint 4 (May 18-May 29): History + Scheduling + Mastery

#### Epic H: Attempt History (PRD Feature 7)
- Story H1: Subtopic attempt timeline ordered by date.
- Story H2: Trend indicator for score progression.

#### Epic I: Spaced Repetition (PRD Feature 8)
- Story I1: Generate default review schedule (24h, 3d, 7d, 14d, 30d) after first attempt.
- Story I2: Accelerate schedule for low performance (levels 0-2).
- Story I3: Surface next review date and overdue status.

#### Epic J: Mastery Threshold (PRD Feature 9)
- Story J1: Implement mastery rule: Level >=4 in two attempts on different days.
- Story J2: Persist mastery state + mastery date.
- Story J3: Render mastery badge in dashboard and subtopic view.

#### Engineering Tasks
- Data model: `review_schedules`, `mastery_status`.
- API: `GET /subtopics/:id/history`, `GET /reviews/due`, `POST /scheduling/recompute/:subtopicId`, `GET /subtopics/:id/mastery`.
- Tests: schedule generation unit tests, mastery rule edge-case tests.

### Sprint 5 (Jun 1-Jun 12): Dashboard + Notifications + Stabilization

#### Epic K: Progress Dashboard (PRD Feature 10)
- Story K1: Show total topics, in-progress, mastered, due-today counts.
- Story K2: Show weakest subtopics and optional score trend chart.
- Story K3: Ensure dashboard updates after each attempt.

#### Epic L: Reminders (PRD Feature 11)
- Story L1: In-app notification list for due reviews.
- Story L2: Deep-link reminder item to target recall session.
- Story L3: Optional email reminder stub behind feature toggle.

#### Epic M: Hardening + Launch Readiness
- Story M1: Add analytics events for activation and learning loop.
- Story M2: Add rate limits and retry/backoff for AI calls.
- Story M3: Complete E2E regression suite for core flows.
- Story M4: Execute beta checklist and release candidate sign-off.

#### Engineering Tasks
- API: `GET /dashboard`, `GET /notifications`, `POST /notifications/:id/read`.
- Observability: tracing, error alerts, job queue metrics.
- Tests: full flow E2E (upload -> structure -> recall -> review due -> mastery).

## Acceptance Gates Before MVP Release
- All 11 PRD features meet acceptance criteria.
- Upload/process/evaluation/scheduling failures have user-visible recovery states.
- Core flow success rate and latency are within agreed MVP targets.
- No open P0/P1 defects in release candidate.

## Risks and Mitigations
- AI output variability: enforce strict response schema + retries + fallback prompts.
- File extraction failures: validate MIME upfront and return clear remediation messages.
- Scheduling edge cases: deterministic date math with timezone-safe tests.
- Scope creep: keep optional items (`timer`, `email reminders`, `trend chart`) behind flags.
