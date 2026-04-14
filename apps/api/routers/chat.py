"""Chat router stubs. Phase 3 implements the real /chat/stream and /chat/ephemeral."""

from fastapi import APIRouter, Request, status

from models.chat import ChatRequest, EphemeralResponseRequest

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/stream", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def chat_stream(request: Request, body: ChatRequest) -> dict:
    return {
        "error": {
            "code": "not_implemented",
            "message": "chat/stream is implemented in Phase 3 (T038)",
            "recoverable": False,
        }
    }


@router.post("/ephemeral", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def chat_ephemeral(request: Request, body: EphemeralResponseRequest) -> dict:
    return {
        "error": {
            "code": "not_implemented",
            "message": "chat/ephemeral is implemented in Phase 3 (T043)",
            "recoverable": False,
        }
    }
