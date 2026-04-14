"""Conversation router stubs. Phase 4 implements list/detail/archive (T058–T060)."""

from fastapi import APIRouter, Request, status

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def list_conversations(request: Request) -> dict:
    return {
        "error": {
            "code": "not_implemented",
            "message": "conversations list is implemented in Phase 4 (T058)",
            "recoverable": False,
        }
    }


@router.get("/{conversation_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_conversation(conversation_id: str, request: Request) -> dict:
    return {
        "error": {
            "code": "not_implemented",
            "message": "conversations detail is implemented in Phase 4 (T059)",
            "recoverable": False,
        }
    }


@router.delete("/{conversation_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def archive_conversation(conversation_id: str, request: Request) -> dict:
    return {
        "error": {
            "code": "not_implemented",
            "message": "conversations archive is implemented in Phase 4 (T060)",
            "recoverable": False,
        }
    }
