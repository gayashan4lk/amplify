"""Content generation REST endpoints.

Scaffolded here so the app bootstrap (T014) can mount the router. The
endpoint handlers are implemented per-story in T032-T034 (US1), T045 (US2),
and T058 (cross-cutting).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/content", tags=["content"])
