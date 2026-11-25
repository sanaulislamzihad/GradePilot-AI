# Project Progress

A feature is marked done only when it is implemented, tested and working end to end.

**Legend:** ✅ done · 🔄 in progress · ⬜ not started

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Foundation: setup, database, authentication, roles, dashboards | ✅ Done |
| 2 | Exam management: creation, question paper, questions, marks, answers, rubrics, publishing | ✅ Done |
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

## Phase 2 — Exam management ✅

### Database
- ✅ `exams`, `questions` (with one level of sub-questions), `model_answers`, `rubrics`,
  `rubric_criteria`, `exam_documents`; Alembic migration verified on SQLite and rendered for PostgreSQL
- ✅ Exact decimal marks; string-backed enums so new values need no PostgreSQL type change

### Exam creation
- ✅ Seven-step workspace: details → question paper → questions → marks → model answers → rubrics → publish
- ✅ Exam information: title, type, course and section (ownership-checked), exam date,
  deadline, total marks, instructions, allowed formats, maximum file size, maximum attempts
- ✅ Exam list with search, status filter and pagination; teacher dashboard exam counts

### Question paper
- ✅ Upload PDF, DOCX, JPG, JPEG, PNG with backend validation (extension, magic bytes,
  image decoding, zip-bomb guard, 20 MB limit) and randomised private storage
- ✅ Direct text extraction from digital PDFs (PyMuPDF) and DOCX (python-docx)
- ✅ Scanned PDFs and images detected and stored as *needs OCR* — nothing is guessed
- ✅ Rule-based detection of question numbers, sub-questions, printed marks and question type
- ✅ Re-extraction requires explicit confirmation before replacing edited questions
- ✅ Authorised download; replaced and deleted files removed from storage

### Questions, marks, model answers and rubrics
- ✅ Edit label, text and type; add, delete, reorder; split a question into parts
- ✅ Marks on gradable questions; parent marks are the sum of their parts; total validated
- ✅ Model answers per question with draft / approve; edits reset approval
- ✅ Model answer document import mapped by question number, with a matching report
- ✅ Rubric criteria editor; approval only when criteria add up to the question marks;
  later mark changes invalidate the approval for publishing

### Publication
- ✅ Readiness checklist (details, questions, marks, model answers, rubrics) enforced on the server
- ✅ Publish / unpublish; published exams are locked against every change
- ✅ Unguessable shareable link, QR code generated in the browser with PNG download
- ✅ Public exam page with details only (no questions, answers or rubrics)
- ✅ Teacher preview of the full paper

### Tests
- ✅ Backend: 92 tests in total — parser unit tests, uploads (valid, spoofed, empty, corrupt,
  oversized), extraction, question editing, marks, model answers, rubrics, publishing,
  locking, public link and ownership
- ✅ Frontend: 24 tests in total — marks totals, rubric approval rule, publish readiness, helpers
- ✅ Full workflow run in a real browser (Edge): create → upload PDF → extract → marks →
  import model answers from DOCX → approve → rubrics → publish → public page

### Deferred to later phases (by design)
- AI extraction for scanned papers and handwriting, AI-drafted model answers and AI-suggested
  rubrics need the AI provider integration (Phase 4). No placeholder buttons are shown for them.
- Students listing available exams in their dashboard and uploading scripts from the exam
  link arrive with Phase 3. The public page currently states that online upload is not yet available.
- Unpublishing will be blocked once an exam has submissions (Phase 3).

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
