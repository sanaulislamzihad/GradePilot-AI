"""Centralised error type and handlers.

Every error response has the shape `{"detail": str}`; validation errors add a
`fields` list so forms can highlight the offending inputs.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("gradepilot")


class AppError(Exception):
    def __init__(self, status_code: int, detail: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.headers = headers


def _field_errors(exc: RequestValidationError) -> list[dict]:
    fields = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", []) if part not in ("body", "query", "path")]
        message = str(error.get("msg", "Invalid value")).removeprefix("Value error, ")
        fields.append({"field": ".".join(location) or None, "message": message})
    return fields


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = _field_errors(exc)
        summary = fields[0]["message"] if len(fields) == 1 else "Some fields are invalid"
        return JSONResponse(
            {"detail": summary, "fields": fields}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    @app.exception_handler(SQLAlchemyError)
    async def _database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        # Log the type only; statements can contain user data.
        logger.error("Database error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
        return JSONResponse(
            {"detail": "A database error occurred. Please try again."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
