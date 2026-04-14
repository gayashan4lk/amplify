"""X-User-Id trust middleware per SAD §6.3.

Next.js is the only auth authority. FastAPI is only reachable over Railway's
private network and trusts the X-User-Id header set by the Next.js API client.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

# Paths that do NOT require X-User-Id. Keep this list exhaustively small.
_EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class UserIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        if any(path == p or path.startswith(p + "/") for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        user_id = request.headers.get("X-User-Id")
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "unauthenticated",
                        "message": "Missing X-User-Id header.",
                        "recoverable": False,
                    }
                },
            )
        request.state.user_id = user_id
        return await call_next(request)
