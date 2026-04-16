"""T029: FastAPI OpenAPI output exposes the documented endpoints with the
contract shapes from rest-endpoints.md."""

from fastapi.testclient import TestClient

from main import app


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_openapi_exposes_documented_paths():
    client = _client()
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert "/api/v1/chat/stream" in paths
    assert "post" in paths["/api/v1/chat/stream"]
    assert "/api/v1/chat/ephemeral" in paths
    assert "post" in paths["/api/v1/chat/ephemeral"]
    assert "/api/v1/conversations" in paths
    assert "get" in paths["/api/v1/conversations"]
    assert "/api/v1/conversations/{conversation_id}" in paths
    detail = paths["/api/v1/conversations/{conversation_id}"]
    assert "get" in detail and "delete" in detail


def test_chat_stream_request_shape_in_schema():
    client = _client()
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]
    assert "ChatRequest" in schemas
    props = schemas["ChatRequest"]["properties"]
    assert "conversation_id" in props
    assert "message" in props
    assert schemas["ChatRequest"]["required"] == ["message"]


def test_missing_user_id_returns_401():
    client = _client()
    # Any non-exempt endpoint without X-User-Id must 401 via the middleware.
    resp = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": None, "message": "hi"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "unauthenticated"


def test_health_is_exempt_from_auth():
    client = _client()
    resp = client.get("/health")
    assert resp.status_code == 200
