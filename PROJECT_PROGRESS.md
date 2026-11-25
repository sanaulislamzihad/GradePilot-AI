# Project Progress

A feature is marked done only when it is implemented, tested and working end to end.

**Legend:** ✅ done · 🔄 in progress · ⬜ not started

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Foundation: setup, database, authentication, roles, dashboards | ✅ Done |
| 2 | Exam management | ⬜ |
| 3 | Student submission | ⬜ |
| 4 | AI integration | ⬜ |
| 5 | Advanced evaluation | ⬜ |
| 6 | Results and analytics | ⬜ |
| 7 | Production readiness | ⬜ |

---

## Phase 1 — Foundation ✅

### Project setup
- ✅ Monorepo layout (`backend/`, `frontend/`, `storage/`), `.gitignore`, `.gitattributes`
- ✅ `.env.example` with placeholders only; API refuses to start with a weak JWT secret
- ✅ FastAPI app with CORS, security headers and centralised JSON error handling
- ✅ Vite + React 19 + TypeScript (strict) + Tailwind CSS v4, ESLint, Vitest

### Database
- ✅ SQLAlchemy 2.0 models: `users`, `refresh_tokens`, `courses`, `course_sections`,
  `section_enrollments`, `audit_logs`
- ✅ UUID primary keys, foreign keys with cascade rules, unique constraints, indexes, timestamps
- ✅ Alembic migration; verified on SQLite and rendered for PostgreSQL
- ✅ Test that the migration history matches the models exactly
- ✅ UTC-normalised timestamps on every database backend

### Authentication
- ✅ Register (teacher / student), login, logout, current user
- ✅ Argon2id password hashing with timing-safe handling of unknown emails
- ✅ Short-lived JWT access tokens (in memory on the client)
- ✅ Rotating opaque refresh tokens in an httpOnly cookie, stored hashed
- ✅ Reuse detection revokes the whole session family; concurrent tabs handled safely
- ✅ Password change signs out every other device
- ✅ Rate limiting on credential endpoints
- ✅ CLI command to create administrator accounts

### Role-based access control
- ✅ Admin, teacher and student roles enforced on every endpoint
- ✅ Role is read from the database, not trusted from the token
- ✅ Role change and deactivation end existing sessions immediately
- ✅ Teachers access only their own courses; students only their own enrollments

### Courses and sections (groundwork for exams)
- ✅ Teacher course CRUD with search and pagination
- ✅ Sections with generated join codes, open/close, code rotation
- ✅ Students join with a code (one section per course), leave a section
- ✅ Teacher roster view and student removal

### Dashboards and pages
- ✅ Landing, login, register, 404
- ✅ Teacher: dashboard (live counts, recent activity), courses, course detail, profile
- ✅ Student: dashboard, my courses (join / leave), profile
- ✅ Admin: overview, user management (role / status), audit log, system status, profile
- ✅ Responsive layout with mobile navigation; monochrome design, no gradients
- ✅ Navigation lists only implemented pages — no placeholder links

### Tests
- ✅ Backend: 59 tests — auth, refresh rotation and reuse, rate limiting, role matrix,
  ownership, enrollment rules, dashboard counts, admin rules, audit log, migrations
- ✅ Frontend: 15 tests — route guards, login, registration validation, API error handling
- ✅ Manual end-to-end run in a real browser (Edge) for every role, including session
  restore after a full page reload

### Known limitations (planned)
- Rate limiting is per process; it moves to Redis in Phase 7.
- Local development uses SQLite. PostgreSQL works through `DATABASE_URL` and the migration
  renders correctly for it, but has not yet been run against a live PostgreSQL server
  (Docker Compose arrives in Phase 7).
- Email verification and password reset by email are not implemented.

---

## Phase 2 — Exam management ⬜
- ⬜ Exam model and multi-step creation wizard (information, deadlines, policies)
- ⬜ Question paper upload (PDF, DOCX, images) with secure private storage
- ⬜ Text extraction (PyMuPDF, python-docx) and editable question list
- ⬜ Mark allocation with total validation
- ⬜ Model answers (upload or AI draft with approval)
- ⬜ Rubric editor with per-question total validation
- ⬜ Draft, preview, publish, unique exam link and QR code

## Phase 3 — Student submission ⬜
- ⬜ Exam access by link or dashboard; available exams for enrolled sections
- ⬜ Script upload with backend validation (type, MIME, size, deadline, attempts)
- ⬜ Submission records, IDs and status tracking

## Phase 4 — AI integration ⬜
- ⬜ Provider adapters and central AI router
- ⬜ BYOK settings with AES-256-GCM encrypted keys, masked display, connection test
- ⬜ Model slots: OCR / evaluator / verifier
- ⬜ Document extraction and rubric-based evaluation with feedback

## Phase 5 — Advanced evaluation ⬜
- ⬜ Independent verification, SymPy maths checks, review flags
- ⬜ Teacher review dashboard with audit trail

## Phase 6 — Results and analytics ⬜
- ⬜ Result publication modes, student result page, PDF reports
- ⬜ Analytics dashboard with Recharts, CSV export

## Phase 7 — Production readiness ⬜
- ⬜ Redis + background workers, Docker Compose, deployment guide
- ⬜ Security review and performance work
