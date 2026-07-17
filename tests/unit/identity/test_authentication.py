from __future__ import annotations

import httpx

from apps.api.main import create_app
from apps.api.settings import Settings


async def test_protected_request_rejects_missing_authenticator() -> None:
    app = create_app(settings=Settings(_env_file=None, environment="test"))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v2/projects")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


async def test_identity_headers_cannot_impersonate_an_actor() -> None:
    app = create_app(settings=Settings(_env_file=None, environment="test"))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v2/projects",
            headers={
                "X-Organization-Id": "01900000-0000-7000-8000-000000000001",
                "X-User-Id": "01900000-0000-7000-8000-000000000002",
                "X-Principal-Id": "01900000-0000-7000-8000-000000000002",
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_runtime_openapi_declares_cookie_security_on_protected_routes() -> None:
    app = create_app(settings=Settings(_env_file=None, environment="test"))
    openapi = app.openapi()
    scheme = openapi["components"]["securitySchemes"]["cookieAuth"]
    assert scheme["type"] == "apiKey"
    assert scheme["in"] == "cookie"
    assert scheme["name"] == "shanhai_session"

    for operation_id in (
        "createProject",
        "listProjects",
        "getProject",
        "createMaterialUploadSession",
        "confirmMaterialUpload",
        "getGenerationJob",
        "cancelGenerationJob",
        "streamGenerationJobEvents",
        "streamProjectEvents",
    ):
        operation = next(
            operation
            for path_item in openapi["paths"].values()
            for operation in path_item.values()
            if operation.get("operationId") == operation_id
        )
        assert operation["security"] == [{"cookieAuth": []}]
