"""GradePilot AI API entry point."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import (
    admin,
    ai_assist,
    ai_settings,
    auth,
    courses,
    dashboard,
    evaluations,
    exams,
    health,
    public,
    results,
    student,
    submissions,
    users,
)
from app.core.config import get_settings
from app.core.errors import register_exception_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=__version__,
        # Interactive docs are useful locally but are not exposed in production.
        docs_url=None if settings.environment == "production" else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.environment == "production" else "/api/openapi.json",
    )

    max_body = settings.max_request_size_mb * 1024 * 1024
    production = settings.environment == "production"
    docs_paths = ("/api/docs", "/api/openapi.json")

    @app.middleware("http")
    async def _request_limits_and_headers(request: Request, call_next):
        # Reject oversized bodies before reading them (the proxy enforces the same limit
        # for requests without a Content-Length header).
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > max_body:
            return JSONResponse(
                {"detail": f"The request is too large. The limit is {settings.max_request_size_mb} MB."},
                status_code=413,
            )
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if not request.url.path.startswith(docs_paths):
            # The API only returns data and files, never pages that run scripts.
            headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if production:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    # Added last so it is the outermost layer: error responses (413, 429) keep their CORS headers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    register_exception_handlers(app)

    for module in (health, auth, users, courses, exams, submissions, evaluations, results, ai_settings, ai_assist, public, student, dashboard, admin):
        app.include_router(module.router, prefix=settings.api_prefix)

    return app


app = create_app()
