# Project Progress

A feature is marked done only when it is implemented, tested and working end to end.

**Legend:** ✅ done · 🔄 in progress · ⬜ not started

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Foundation: setup, database, authentication, roles, dashboards | ✅ Done |
| 2 | Exam management: creation, question paper, questions, marks, answers, rubrics, publishing | ✅ Done |
| 3 | Student submission: exam access, script upload, attempts, submission records | ✅ Done |
| 4 | AI integration: BYOK, provider adapters, router, extraction, evaluation, background jobs | ✅ Done |
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
- Student exam listing and script upload were delivered in Phase 3.

## Phase 3 — Student submission ✅

### Database
- ✅ `submissions` (reference code, attempt number, latest flag, status, student ID snapshot,
  idempotency key) and `submission_files`; unique attempt per exam and student
- ✅ Status field covers the full lifecycle (uploaded → … → published / failed)

### Access
- ✅ Shared link and QR code lead to the student exam page; signing in or registering returns
  the student to the exam
- ✅ Available Exams lists published exams for the student's sections
- ✅ Course- and section-linked exams accept only enrolled students; link-only exams accept any student
- ✅ Exam page shows title, course, section, teacher, total marks, deadline, instructions,
  accepted files, attempts and submission status, with a clear reason when submitting is not possible

### Upload
- ✅ One PDF (up to 100 pages) or ordered page images (up to 30), reorderable before upload
- ✅ Backend validation: exam formats, real file type, image decoding, per-file size limit,
  total size, damaged or password-protected PDFs, deadline, attempt limit, enrollment
- ✅ Upload progress, confirmation dialog and a receipt with submission ID, time and status
- ✅ Duplicate protection: idempotency key reused on retry, identical files refused,
  concurrent duplicates resolved by database constraints, stored files cleaned up on failure
- ✅ Replacement attempts only while the policy allows; earlier attempts kept and marked replaced

### Records and views
- ✅ Student: My Submissions (with replaced attempts) and submission detail with in-app file preview
- ✅ Teacher: Submissions list filtered by exam and status, search by name, student ID or
  submission ID; detail with student details and file preview / download
- ✅ Submission counts on exam list, publish step and dashboards; student dashboard shows
  available, submitted and upcoming exams
- ✅ Exams with submissions cannot be unpublished
- ✅ Every submission recorded in the audit log

### Fixed along the way
- ✅ Signing in from a protected page now returns to that page (the guest-only route guard
  previously sent every user to their dashboard)

### Tests
- ✅ Backend: 113 tests in total — 21 new for submissions (happy path, images, multi-page PDF,
  attempts, idempotency, invalid and encrypted files, size and format policy, deadline,
  enrollment, drafts, roles, privacy, search, unpublish lock, dashboards)
- ✅ Frontend: 30 tests in total — script picker rules, blocked reasons, upload retry with the
  same idempotency key, receipt, return after sign-in
- ✅ Full flow in a real browser (Edge): shared link → sign in → upload PDF → receipt →
  dashboard → submission preview → teacher submissions list and detail

### Deferred to later phases (by design)
- Background processing was delivered in Phase 4.

## Phase 4 — AI integration ✅

### Keys and providers
- ✅ AES-256-GCM encryption with key ids for rotation; associated data binds a key to its owner and provider
- ✅ Keys tested before saving (rejected keys never stored), masked hints only, replace and delete, re-test
- ✅ Adapters for Gemini, OpenAI, Anthropic Claude (official SDK), DeepSeek, Groq, OpenRouter,
  plus an optional custom OpenAI-compatible endpoint (off by default)
- ✅ Adapters never fall back to ambient server credentials; keys never appear in URLs or logs
- ✅ Usage log per request (task, model, tokens, latency, outcome, cost when reported) with per-provider totals

### Model slots and router
- ✅ OCR, evaluator and verifier slots; same model allowed in several slots; live model lists
- ✅ Capability check with real probes: listed by provider, text, JSON, image input, context window
- ✅ Central router: per-request key decryption, retries with backoff for rate limits, timeouts
  and outages, no retry for permanent errors, structured output validation with one corrective retry

### Pipeline
- ✅ Extraction from PDF text layers with the local parser; AI splitting only when labels are missing
- ✅ OCR of scans and photos: EXIF rotation, grayscale, CLAHE contrast, resizing, batched pages
- ✅ Label normalisation, continued answers joined, missing answers recorded
- ✅ Teacher review when confidence is low, text is unreadable or does not match a question;
  teacher corrections and confirmation before marking
- ✅ Rubric-based evaluation per question with evidence, explanations, missing concepts and feedback
- ✅ Backend score validation: criterion ids, 0..max bounds, evidence checked against the answer,
  totals computed by the backend, no total when a question is ungraded
- ✅ Prompt-injection guard: student text passed as data with instructions to ignore commands in it
- ✅ Celery jobs (Redis in production, SQLite broker locally), automatic processing on upload,
  compare-and-set status claims so no submission is processed twice, visible failures with retry
- ✅ AI reading of scanned question papers; AI-drafted model answers and rubrics saved as unapproved drafts

### Frontend
- ✅ AI Settings page: provider keys, model slots, capability checks, usage
- ✅ Submission processing panel with live status updates, extracted answer review, AI-suggested marks view
- ✅ AI drafting buttons in exam setup, shown only when a suitable model is configured
- ✅ Process all pending submissions of an exam

### Tests
- ✅ Backend: 156 tests in total — encryption, every adapter's request shape and error mapping,
  BYOK API, router retries and validation, and the pipeline cases from the spec (correct, partial,
  incorrect, alternative wording, missing, unreadable, out-of-scope) with a mock provider
- ✅ Frontend: 33 tests in total — key entry, AI marks view, extraction review
- ✅ Full flow in a real browser with a real Celery worker and a local OpenAI-compatible stub
  model: connect a provider, configure and check slots, automatic processing of a digital
  script and a photographed script, OCR review and confirmation, AI marks, student view without marks

### Not done in this phase
- Verifier slot is configurable, but independent verification runs from Phase 5.
- Mathematical verification with SymPy and similarity signals from Sentence Transformers are Phase 5.
- No real provider was called during development (no keys were available); adapters are tested
  against recorded request and response shapes. Run **Check capabilities** after connecting a real key.

## Phase 5 — Advanced evaluation ⬜
- ⬜ Independent verification, SymPy maths checks, review flags
- ⬜ Teacher review dashboard with audit trail

## Phase 6 — Results and analytics ⬜
- ⬜ Result publication modes, student result page, PDF reports
- ⬜ Analytics dashboard with Recharts, CSV export

## Phase 7 — Production readiness ⬜
- ⬜ Redis + background workers, Docker Compose, deployment guide
- ⬜ Security review and performance work
