# GradePilot AI

**Intelligent Automated Examination Script Evaluation System**
*Smarter Checking. Fairer Grading. Faster Feedback.*

GradePilot AI helps teachers mark examination scripts against a rubric they approve.
The AI suggests marks with evidence for every criterion; teachers review, adjust and
publish the final result. AI marks are never treated as final on their own.

The project is built in phases. **Phase 1 (foundation) is complete**: authentication,
role-based access control, course and section management, and dashboards for teachers,
students and administrators. See [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) for the
status of every phase.

---

## Tech stack

| Layer     | Technology |
|-----------|------------|
| Frontend  | React 19, Vite, TypeScript, Tailwind CSS v4, React Router, React Hook Form, Zod, Radix UI, Lucide |
| Backend   | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic |
| Database  | PostgreSQL (production) · SQLite (local development and tests) |
| Security  | Argon2id password hashing, short-lived JWT access tokens, rotating httpOnly refresh cookies |
| Testing   | pytest, FastAPI TestClient · Vitest, Testing Library |

Planned for later phases: Redis with a background job queue, AI provider adapters
(Gemini, OpenAI, Claude, DeepSeek, Groq, OpenRouter), PyMuPDF, OpenCV, Sentence
Transformers, SymPy, Recharts and Docker Compose.

## Repository layout

```
GradePilot AI/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers and dependencies (auth, RBAC)
│   │   ├── core/           # settings and error handling
│   │   ├── database/       # engine, session, declarative base
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic request and response models
│   │   ├── security/       # password hashing, tokens, rate limiting
│   │   ├── services/       # business rules (auth sessions, courses, audit)
│   │   ├── cli.py          # administrative commands
│   │   └── main.py         # application entry point
│   ├── migrations/         # Alembic migrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/     # reusable UI components
│       ├── contexts/       # auth context
│       ├── hooks/
│       ├── layouts/        # app shell, navigation, route guards
│       ├── pages/          # auth, teacher, student, admin, shared
│       ├── services/       # HTTP client and typed API calls
│       ├── types/
│       └── utils/
├── storage/                # private uploads (git-ignored)
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

To use PostgreSQL, set for example
`DATABASE_URL=postgresql+psycopg://gradepilot:password@localhost:5432/gradepilot`.

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Interactive API documentation is served at <http://localhost:8000/api/docs>
(disabled when `ENVIRONMENT=production`).

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
- Credential endpoints are rate limited (in-process for now; moves to Redis in Phase 7).

## API overview (Phase 1)

| Area | Endpoints |
|------|-----------|
| Auth | `POST /api/auth/register` · `POST /api/auth/login` · `POST /api/auth/refresh` · `POST /api/auth/logout` · `GET /api/auth/me` |
| Profile | `PATCH /api/users/me` · `POST /api/users/me/password` |
| Courses (teacher) | `GET/POST /api/courses` · `GET/PUT/DELETE /api/courses/{id}` · `POST /api/courses/{id}/sections` |
| Sections (teacher) | `PATCH/DELETE /api/sections/{id}` · `POST /api/sections/{id}/join-code` · `GET /api/sections/{id}/students` · `DELETE /api/sections/{id}/students/{enrollment_id}` |
| Enrollment (student) | `GET/POST /api/student/enrollments` · `DELETE /api/student/enrollments/{id}` |
| Dashboards | `GET /api/dashboard/teacher` · `GET /api/dashboard/student` |
| Admin | `GET /api/admin/overview` · `GET /api/admin/users` · `PATCH /api/admin/users/{id}` · `GET /api/admin/audit-logs` · `GET /api/admin/system` |
| Health | `GET /api/health` |

## License

[MIT](LICENSE)
