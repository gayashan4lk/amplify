"""FastAPI app entrypoint.

Private-network only — the X-User-Id trust middleware runs on every non-exempt
request. Next.js is the sole auth authority.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from middleware.auth import UserIdMiddleware
from routers import chat as chat_router
from routers import conversations as conv_router

log = logging.getLogger("amplify.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("LANGSMITH_TRACING", "").lower() == "true":
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGSMITH_PROJECT", "amplify-dev"))
        log.info("langsmith tracing enabled project=%s", os.environ["LANGCHAIN_PROJECT"])

    # Prisma / Motor / Redis clients are constructed lazily per-request in
    # Phase 3. Keeping lifespan empty here avoids forcing real DB creds at
    # import time during contract tests.
    yield


app = FastAPI(title="Amplify API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("WEB_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)
app.add_middleware(UserIdMiddleware)

app.include_router(chat_router.router)
app.include_router(conv_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
