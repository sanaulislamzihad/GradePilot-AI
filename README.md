# GradePilot AI

**Intelligent Automated Examination Script Evaluation System**
*Smarter Checking. Fairer Grading. Faster Feedback.*

GradePilot AI helps teachers mark examination scripts against a rubric they approve.
The AI suggests marks with evidence for every criterion; teachers review, adjust and
publish the final result. AI marks are never treated as final on their own.

The project was built in seven phases, **all complete**:

- **Phase 1 — Foundation:** authentication, role-based access control, course and section
  management, and dashboards for teachers, students and administrators.
- **Phase 2 — Exam management:** exam creation, question paper upload and text extraction,
  editable questions and sub-questions, mark allocation, model answers, marking rubrics,
  and publishing with a shareable link and QR code.
- **Phase 3 — Student submission:** exam access by link or dashboard, answer script upload
  (one PDF or page images), attempt limits, duplicate protection, submission records and
  teacher submission views.
- **Phase 4 — AI integration:** bring-your-own-key provider settings with encrypted keys,
  six provider adapters behind one AI router, model slots with live capability checks,
  answer extraction (text layer or OCR), rubric-based evaluation with backend score
  validation, background processing with Celery, and AI drafting of model answers and rubrics.
- **Phase 5 — Advanced evaluation:** independent verification by a second model, SymPy
  checks of mathematical answers, a local semantic-similarity signal, review flags, and the
  teacher review workflow (overrides, comments, approval, re-marking, change history).
- **Phase 6 — Results and analytics:** result release modes (after approval or provisional),
  publishing and withdrawing results, a student results area, PDF result reports, CSV export,
  and class analytics from teacher-approved marks.
- **Phase 7 — Production readiness:** a security review (production configuration guard,
  shared Redis rate limits, security headers, request size limits), Docker images and a
  Compose stack, the full test suite verified on PostgreSQL, query and bundle-size work,
  and a deployment guide.

See [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) for the status of every phase.

---

## Tech stack

| Layer     | Technology |
|-----------|------------|
| Frontend  | React 19, Vite, TypeScript, Tailwind CSS v4, React Router, React Hook Form, Zod, Radix UI, Lucide |
| Backend   | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic |
| Documents | PyMuPDF (PDF text and page rendering, PDF reports with embedded Noto Sans from `pymupdf-fonts`), python-docx, Pillow, OpenCV (image preprocessing) |
| AI        | Provider adapters for Gemini, OpenAI, Anthropic Claude (official SDK), DeepSeek, Groq, OpenRouter; AES-256-GCM key encryption (`cryptography`) |
| Jobs      | Celery — Redis broker in production, SQLite-backed broker for local development |
| Database  | PostgreSQL (production) · SQLite (local development and tests) |
| Security  | Argon2id password hashing, short-lived JWT access tokens, rotating httpOnly refresh cookies |
| Testing   | pytest, FastAPI TestClient · Vitest, Testing Library |
| Other     | `qrcode` (QR codes generated in the browser, no external service) |

| Local checks | SymPy (symbolic answer checks), Sentence Transformers all-MiniLM-L6-v2 (similarity, CPU, no API key) |

Charts are small hand-written SVG components (no chart library). Deployment uses Docker Compose with
PostgreSQL 16, Redis 7 and nginx.

## Repository layout

```
GradePilot AI/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers and dependencies (auth, RBAC, rate limits)
│   │   ├── core/           # settings and error handling
│   │   ├── database/       # engine, session, declarative base
│   │   ├── models/         # SQLAlchemy models
│   │   ├── providers/      # AI provider adapters
│   │   ├── schemas/        # Pydantic request and response models
│   │   ├── security/       # password hashing, tokens, encryption, rate limiting
│   │   ├── services/       # business rules (exams, marking, review, results, reports)
│   │   ├── tasks/          # Celery application and background jobs
│   │   ├── cli.py          # administrative commands
│   │   └── main.py         # application entry point
│   ├── migrations/         # Alembic migrations
│   ├── tests/
│   ├── Dockerfile          # one image for the API, worker and migrations
│   └── docker-entrypoint.sh
├── frontend/
│   ├── src/
│   │   ├── components/     # reusable UI components and charts
│   │   ├── contexts/       # auth context
│   │   ├── hooks/
│   │   ├── layouts/        # app shell, navigation, route guards
│   │   ├── pages/          # auth, teacher, student, admin, shared
│   │   ├── services/       # HTTP client and typed API calls
│   │   ├── types/
│   │   └── utils/
│   ├── docker/             # nginx config and security headers for the production image
│   └── Dockerfile
├── storage/                # private uploads (git-ignored)
├── docker-compose.yml      # production stack
├── .env.example
├── PROJECT_PROGRESS.md
└── README.md
```

## Getting started

### Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- PostgreSQL 14+ (optional for local development; SQLite is used by default)

### 1. Configure the environment

```bash
cp .env.example .env
```

Set `JWT_SECRET_KEY` to a random value (the API refuses to start with a weak secret):

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Set `ENCRYPTION_KEYS` so teachers can store AI provider keys (AES-256-GCM, 32-byte key):

```bash
python -c "import os,base64; print('k1:' + base64.b64encode(os.urandom(32)).decode())"
```

To rotate, put the new key first and keep the old one after it (`k2:...,k1:...`).

To use PostgreSQL, set for example
`DATABASE_URL=postgresql+psycopg://gradepilot:password@localhost:5432/gradepilot`.

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt --extra-index-url https://download.pytorch.org/whl/cpu
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Interactive API documentation is served at <http://localhost:8000/api/docs>
(disabled when `ENVIRONMENT=production`).

Start the background worker in a second terminal (it reads and marks scripts):

```bash
celery -A app.tasks.celery_app worker --loglevel=info              # Linux / macOS
celery -A app.tasks.celery_app worker --loglevel=info --pool=solo  # Windows
```

Without `CELERY_BROKER_URL` the worker uses a local SQLite broker; in production point it
at Redis (`CELERY_BROKER_URL=redis://localhost:6379/0`).

Create the first administrator (the password is prompted for, never passed as an argument):

```bash
python -m app.cli create-admin --email admin@your-institution.edu --name "System Admin"
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to the backend, so the
refresh-token cookie stays same-origin.

## Running tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
npm run lint
npm run typecheck
```

The test suites need no external services and no API keys.

The backend suite runs on SQLite by default. To run the same tests against PostgreSQL,
point `TEST_DATABASE_URL` at an **empty** database (it is migrated, then cleaned after each test):

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/gradepilot_test pytest
```

## Authentication and security model

- **Roles**: `admin`, `teacher`, `student`. Teachers and students self-register; admins
  are created with the CLI. Each role has its own dashboard and API surface, enforced on
  the server for every request.
- **Access tokens** are short-lived JWTs held only in memory by the browser.
- **Refresh tokens** are random opaque values stored as SHA-256 hashes. They live in an
  `httpOnly`, `SameSite=Strict` cookie scoped to `/api/auth`, rotate on every use, and a
  replayed old token revokes the whole session family.
- **Instant revocation**: password changes, role changes and deactivation bump a token
  version, so existing access tokens stop working immediately.
- **Ownership**: teachers can only see and change their own courses; students can only
  see their own enrollments. Cross-account access returns 404.
- **Audit log**: sign-ins, profile changes, admin actions and course changes are recorded
  without passwords, tokens or other secrets.
- **Rate limits**: sign-in, registration and password changes per client address; answer
  script uploads per student; requests that start AI work per user. With
  `RATE_LIMIT_REDIS_URL` every API worker shares one count in Redis (Docker Compose sets
  this); without it each process counts on its own, which suits a single worker. If Redis
  is unreachable, requests are allowed and the problem is logged rather than locking users out.
- **Production guard**: with `ENVIRONMENT=production` the API refuses to start unless
  cookies are secure, encryption keys are set, and the database and job broker are
  PostgreSQL and Redis. API docs are not served in production.
- **Headers and limits**: API responses carry `Content-Security-Policy: default-src 'none'`,
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` and, in
  production, HSTS. The nginx image adds a strict CSP for the app itself (scripts only from
  the same origin). Request bodies above `MAX_REQUEST_SIZE_MB` (60 MB) are refused.
- **Client addresses behind a proxy**: the API trusts `X-Forwarded-For` only because the
  nginx container overwrites it with the real client address; the API container is not
  reachable from outside. See the deployment guide when adding another proxy in front.
- **Uploads**: file type is decided from the file's bytes and must match its extension;
  images are fully decoded and DOCX archives are checked against zip bombs. Files are saved
  under random names in private storage and served only through an authorised endpoint.
- **Published exams are locked**: questions, marks, answers and rubrics cannot change while
  students can see the exam. The public exam link shows details only — never questions,
  model answers or rubrics.

## Deployment with Docker (Phase 7)

The Compose stack runs six services: **db** (PostgreSQL 16), **redis** (job queue and shared
rate limits, append-only so queued jobs survive restarts), **migrate** (applies migrations
once and exits), **api** (FastAPI, two workers), **worker** (Celery) and **web** (nginx serving
the built frontend and proxying `/api`). The API and worker start only after migrations
succeed. The containers run as unprivileged users.

### First start

```bash
cp .env.example .env
```

In `.env`, set real values for:

| Variable | How to generate |
|----------|-----------------|
| `JWT_SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `ENCRYPTION_KEYS` | `python -c "import os,base64; print('k1:' + base64.b64encode(os.urandom(32)).decode())"` |
| `POSTGRES_PASSWORD` | `python -c "import secrets; print(secrets.token_hex(24))"` (letters and digits only) |

Compose sets `ENVIRONMENT=production`, `COOKIE_SECURE=true`, the database URL, Redis URLs and
the storage path itself; the SQLite values in `.env` are ignored by the containers.

```bash
docker compose up -d --build
docker compose exec api python -m app.cli create-admin --email admin@your-institution.edu --name "System Admin"
```

Open <http://localhost:8080> (change with `HTTP_PORT`). Browsers accept secure cookies on
`localhost`, so sign-in works there without HTTPS.

### HTTPS and real deployments

Serve the app over HTTPS before real use: put a TLS-terminating reverse proxy or load balancer
(Caddy, Traefik, a cloud load balancer) in front of the `web` service. Then:

- Let the proxy send HSTS for the app pages (the API already sends it).
- The `web` container overwrites `X-Forwarded-For` with the address it sees. Behind another
  proxy that address is the proxy's, so all users would share one rate limit. Enable nginx's
  realip module in `frontend/docker/nginx.conf` with your proxy's address:
  `set_real_ip_from 10.0.0.0/8; real_ip_header X-Forwarded-For;`
- Keep the `api` service unpublished; only `web` should be reachable.

### Operations

- **Upgrades**: `git pull && docker compose up -d --build`. The `migrate` job applies new
  migrations before the new API starts.
- **Scaling**: raise `API_WORKERS` and `WORKER_CONCURRENCY`, or run more worker containers
  (`docker compose up -d --scale worker=3`). Rate limits stay correct because they live in Redis.
- **Backups**: the database (`docker compose exec db pg_dump -U gradepilot gradepilot > backup.sql`)
  and the `storage` volume (answer scripts and question papers) must be backed up together.
  Keep `ENCRYPTION_KEYS` safe as well: without it, stored provider keys cannot be decrypted.
- **Key rotation**: for `ENCRYPTION_KEYS`, put a new key first and keep the old ones after it
  (`k2:...,k1:...`). Changing `JWT_SECRET_KEY` signs everyone out.
- **Logs**: `docker compose logs -f api worker`. Logs never contain passwords, API keys or
  student answers.
- **Similarity model**: the worker downloads all-MiniLM-L6-v2 (~90 MB) on first use into the
  `model-cache` volume. Set `SIMILARITY_ENABLED=false` on servers without internet access.

## Exam workflow (Phase 2)

1. **Details** — title, type, optional course and section, total marks, deadline and the
   submission policy (allowed formats, size limit, attempts).
2. **Question paper** — upload PDF, DOCX, JPG or PNG. Text is read directly from digital
   PDFs and DOCX files. Scanned PDFs and images are stored and marked *needs OCR*; reading
   them needs an OCR-capable AI model, which arrives in Phase 4.
3. **Questions** — numbered questions, sub-questions and printed marks are detected from the
   text (`Q1`, `1.`, `1(a)`, `(b)`, `[5]`, `(5 marks)`). Every question can be edited,
   re-typed, reordered, split into parts or deleted.
4. **Marks** — marks live on gradable questions; the total must equal the exam total.
5. **Model answers** — written per question, or imported from an answer document by
   question number. Imported or edited answers stay unapproved until the teacher approves them.
6. **Rubrics** — criteria with marks per question; approval requires the criteria to add up
   to the question's marks.
7. **Publish** — allowed only when every readiness check passes. Publishing creates an
   unguessable link and a QR code.

## Submission workflow (Phase 3)

- Students reach an exam through its link or QR code (they are asked to sign in and are
  brought back to the exam afterwards), or from **Available Exams**, which lists published
  exams for the sections they have joined.
- Exams linked to a course or section accept scripts only from students enrolled there.
  Exams without a course accept any signed-in student who has the link.
- A script is one PDF (any number of pages up to 100) or one image per page. The server
  checks the exam's allowed formats and size limit, the file's real type, damaged or
  password-protected PDFs, the deadline and the attempt limit.
- Each submission gets an ID such as `GP-K7PM2QXR`. A replacement is a new attempt, allowed
  only while attempts remain and the deadline has not passed; earlier attempts are kept.
- Repeating the same upload (double click, retry after a dropped connection) cannot create
  a second attempt: the client sends an `Idempotency-Key`, and identical files are refused.
- Teachers see each student's current script, can filter by exam and status, search by
  name, student ID or submission ID, and view or download the files. Once an exam has
  submissions it can no longer be unpublished.
- New submissions are stored with status **Received**. Text extraction and evaluation
  (Phase 4) will move them through the rest of the lifecycle.

## AI integration (Phase 4)

### Bring your own key
Teachers connect only the providers they use under **AI Settings**. A key is tested with the
provider before it is saved (a rejected key is never stored), encrypted with AES-256-GCM
using associated data that binds it to its owner and provider, and only a masked hint such as
`…abcd` is ever returned. Keys are decrypted only in the backend, for the duration of one
request. A provider's free tier still needs an API key; a chat subscription does not include
API usage. An OpenAI-compatible server at a custom URL (for example a local model server) can
be enabled with `ALLOW_CUSTOM_AI_ENDPOINTS=true`; keep it off on shared servers.

### Model slots
- **A — OCR and documents:** reads scanned or photographed scripts and question papers.
- **B — Evaluator:** marks answers against the rubric and drafts model answers and rubrics.
- **C — Verifier:** configurable now; independent verification arrives in Phase 5.

Model lists come live from each provider. **Check capabilities** sends two tiny requests (a
JSON reply and a digit drawn in an image) to confirm text, JSON and image support.

### Pipeline
1. **Extraction.** Digital PDFs are read from their text layer and split with the local
   parser. Scans and photos are rotated upright, contrast-enhanced with OpenCV and transcribed
   by the OCR model a few pages at a time. Low confidence, unreadable parts or text that
   matches no question send the submission to **teacher review** instead of being guessed.
2. **Evaluation.** Each answer is marked against its approved rubric. The model must quote
   evidence from the answer for every mark. The backend rejects unknown criteria and scores
   outside 0..max (with one corrective retry), checks every quote against the answer, and
   computes all totals itself. Missing answers score zero without an AI call; unreadable
   answers and rejected output are left for the teacher, and no total is claimed then.
3. **Status.** Students see plain-language status messages only. AI marks are suggestions
   visible to the teacher; review, approval and release come in Phases 5 and 6.

Student text is always passed to models as data, with an instruction to ignore any
instructions it contains. Every request is logged with tokens, latency, outcome and cost
when the provider reports it.

## Verification and teacher review (Phase 5)

After the evaluator marks a submission it moves to **Verifying** before the teacher sees it:

- **Verifier model (slot C).** A second model audits every marked question: was the rubric
  followed, does the quoted evidence support each mark, were valid points or alternative
  answers missed, did the marker assume things the answer does not say. It suggests its own
  mark per criterion. A difference of at least 20% of the question's marks (minimum 1), or
  doubts about the rubric or evidence, becomes a **Verifier disagrees** flag. The two
  examiners' marks are never averaged. Use a different provider or model when you can.
- **SymPy.** For mathematical questions the student's final answer is compared symbolically
  with the model answer (equivalent forms match) and each equation in the working is checked
  against the expected solution. Answers that cannot be parsed are flagged as uncertain.
  Student text is filtered through a strict whitelist before SymPy parses it, because the
  parser evaluates Python.
- **Similarity.** Sentence Transformers (all-MiniLM-L6-v2) runs locally on the CPU with no API
  key. It never sets marks; it flags evaluations where the marks and the answer's closeness to
  the model answer point in opposite directions. The model (~90 MB) downloads on first use;
  set `SIMILARITY_ENABLED=false` to turn it off.

The **AI Evaluation** page lists evaluations awaiting review, flagged ones first, and can
approve every evaluation of an exam that has no flags. On a submission, the teacher can set a
mark per criterion or for the whole question, add comments, approve, send the answers back
for a fresh marking run with a reason, re-run the checks, or reopen an approval before
results are released. AI scores are kept unchanged; the server recalculates every final mark
and validates it against its maximum. Every change is recorded in the review history.

## Results and analytics (Phase 6)

Each exam has a **release setting**, which the teacher can change at any time on the
**Results** page:

- **Release after teacher approval** (default). Students see nothing until the teacher
  approves the evaluation and publishes the result.
- **Show provisional marks.** Students see the AI-suggested marks as soon as marking
  finishes, clearly labelled provisional. Review comments are never shown on provisional
  results, and final marks still need approval and publication.

Publishing stores a snapshot of the approved marks, so a published result never changes
underneath the student. It can be published one at a time or for every approved submission at
once, and it can be withdrawn (which also allows the evaluation to be reopened). An option per
exam controls whether the teacher's review comments are included.

Students find their results under **My Results**: total and percentage, marks and comments
per rubric criterion, feedback, the concepts to work on, and a downloadable PDF. No model,
provider, flag, evidence or model-answer detail is ever sent to a student.

The **Analytics** page uses teacher-approved marks only: average, median, highest and lowest
mark, a score distribution, average score per question, the weakest questions, and the
concepts most often missed (counted once per student). Every chart has a table view. The
teacher can download a class report (PDF) and the marks as CSV; CSV cells that a spreadsheet
would run as a formula are prefixed with an apostrophe.

## API overview

| Area | Endpoints |
|------|-----------|
| Auth | `POST /api/auth/register` · `POST /api/auth/login` · `POST /api/auth/refresh` · `POST /api/auth/logout` · `GET /api/auth/me` |
| Profile | `PATCH /api/users/me` · `POST /api/users/me/password` |
| Courses (teacher) | `GET/POST /api/courses` · `GET/PUT/DELETE /api/courses/{id}` · `POST /api/courses/{id}/sections` |
| Sections (teacher) | `PATCH/DELETE /api/sections/{id}` · `POST /api/sections/{id}/join-code` · `GET /api/sections/{id}/students` · `DELETE /api/sections/{id}/students/{enrollment_id}` |
| Enrollment (student) | `GET/POST /api/student/enrollments` · `DELETE /api/student/enrollments/{id}` |
| Dashboards | `GET /api/dashboard/teacher` · `GET /api/dashboard/student` |
| Admin | `GET /api/admin/overview` · `GET /api/admin/users` · `PATCH /api/admin/users/{id}` · `GET /api/admin/audit-logs` · `GET /api/admin/system` |
| Exams (teacher) | `GET/POST /api/exams` · `GET/PUT/DELETE /api/exams/{id}` · `POST /api/exams/{id}/publish` · `POST /api/exams/{id}/unpublish` |
| Exam documents | `POST /api/exams/{id}/upload-question-paper` · `POST /api/exams/{id}/extract-questions` · `POST /api/exams/{id}/model-answer` · `GET/DELETE /api/exams/{id}/documents/{document_id}` |
| Questions | `POST /api/exams/{id}/questions` · `PATCH/DELETE /api/questions/{id}` · `POST /api/exams/{id}/questions/reorder` · `PUT /api/exams/{id}/marks` |
| Answers and rubrics | `PUT/DELETE /api/questions/{id}/model-answer` · `PUT/DELETE /api/questions/{id}/rubric` |
| Submissions | `POST /api/exams/{id}/submissions` · `GET /api/submissions` · `GET /api/submissions/{id}` · `GET /api/submissions/{id}/files/{file_id}` |
| Student exams | `GET /api/student/exams` · `GET /api/student/exams/{slug}` |
| AI settings | `GET /api/providers` · `POST /api/providers/connect` · `POST /api/providers/test` · `GET /api/providers/models` · `DELETE /api/providers/{id}` · `GET /api/model-configs` · `PUT/DELETE /api/model-configs/{slot}` · `POST /api/model-configs/{slot}/check` · `GET /api/usage` |
| Processing | `POST /api/submissions/{id}/extract` · `POST /api/submissions/{id}/evaluate` · `POST /api/submissions/{id}/retry` · `POST /api/exams/{id}/process-pending` · `GET/PUT /api/submissions/{id}/extracted-answers` |
| Evaluations | `GET /api/submissions/{id}/evaluation` · `GET /api/evaluations/{id}` |
| Review | `GET /api/evaluations` · `PUT /api/evaluations/{id}/review` · `POST /api/evaluations/{id}/approve` · `POST /api/evaluations/{id}/reopen` · `POST /api/evaluations/{id}/reject` · `POST /api/evaluations/{id}/verify` · `GET /api/evaluations/{id}/history` · `POST /api/exams/{id}/approve-unflagged` |
| Results | `GET /api/exams/{id}/results` · `PATCH /api/exams/{id}/release-settings` · `POST /api/results/{submission_id}/publish` · `POST /api/results/{submission_id}/withdraw` · `POST /api/exams/{id}/publish-results` · `GET /api/results/{submission_id}` · `GET /api/results/{submission_id}/pdf` · `GET /api/student/results` |
| Analytics and exports | `GET /api/exams/{id}/analytics` · `GET /api/exams/{id}/results.csv` · `GET /api/exams/{id}/report.pdf` |
| AI drafting | `POST /api/exams/{id}/ocr-question-paper` · `POST /api/questions/{id}/model-answer/generate` · `POST /api/questions/{id}/rubric/suggest` |
| Public | `GET /api/public/exams/{slug}` |
| Health | `GET /api/health` |

## License

[MIT](LICENSE)
