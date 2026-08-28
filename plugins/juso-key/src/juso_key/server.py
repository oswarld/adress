"""MCP stdio server and authenticated Streamable HTTP application."""

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
from typing import Any

import uvicorn
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from .bulk import BulkSearchClient
from .cli import DEFAULT_INDEX_ENV
from .contract import verify_address_with_client, verify_live_address

SERVER_INSTRUCTIONS = (
    "Use verify_korean_address before asserting that Korean address text maps to an official "
    "address, postal code, English address, or building identifier. Only a result with "
    "matchStatus=confirmed and assertable=true may be stated as an official match. For candidate "
    "or unmatched results, never infer or invent an addressKey. BD_MGT_SN is building-level and "
    "does not identify a person, business, or unit."
)

mcp = MCPServer(
    name="juso-key",
    title="Juso Key",
    description=(
        "Official Korean address, postal code, and English address verification through the "
        "Juso search API or a local full-release index."
    ),
    instructions=SERVER_INSTRUCTIONS,
    version="0.2.0",
)


@mcp.tool(
    name="verify_korean_address",
    title="Verify Korean address",
    description=(
        "Verify one South Korean road-name or land-lot address against official Juso data. "
        "Uses a local full-release index when JUSO_BULK_INDEX is configured, otherwise the Juso "
        "search API. Returns a building management number only when the match is safe to assert."
    ),
    annotations=ToolAnnotations(
        title="Verify Korean address",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
    structured_output=True,
)
def verify_korean_address(address: str) -> dict[str, object]:
    """Return an AI-safe official-address verification contract."""

    configured_index = os.environ.get(DEFAULT_INDEX_ENV, "").strip()
    if configured_index:
        index_path = Path(configured_index)
        if not index_path.is_file():
            raise RuntimeError(f"{DEFAULT_INDEX_ENV} does not point to a readable index")
        with BulkSearchClient(index_path) as client:
            return verify_address_with_client(address, client)

    approval_key = os.environ.get("JUSO_API_KEY", "")
    if not approval_key:
        raise RuntimeError(
            f"JUSO_API_KEY or {DEFAULT_INDEX_ENV} is required on the MCP server"
        )
    return verify_live_address(address, approval_key)


def comma_separated_env(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name, "")
    if not value.strip():
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


transport_security = TransportSecuritySettings(
    allowed_hosts=comma_separated_env(
        "MCP_ALLOWED_HOSTS", ["localhost:*", "127.0.0.1:*"]
    ),
    allowed_origins=comma_separated_env("MCP_ALLOWED_ORIGINS", []),
)

_mcp_http_app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    transport_security=transport_security,
    host=os.environ.get("HOST", "127.0.0.1"),
)


async def _json_response(send: Any, status: int, payload: dict[str, object]) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BearerTokenMiddleware:
    """Require a static bearer token without exposing it to MCP tool handlers."""

    def __init__(self, inner_app: Any):
        self.inner_app = inner_app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.inner_app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/health":
            await _json_response(send, 200, {"status": "ok"})
            return
        if path != "/mcp":
            await self.inner_app(scope, receive, send)
            return

        configured_token = os.environ.get("MCP_BEARER_TOKEN", "")
        if not configured_token:
            await _json_response(send, 503, {"error": "MCP_BEARER_TOKEN is not configured"})
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"")
        scheme, separator, supplied_token = authorization.partition(b" ")
        valid = (
            separator == b" "
            and scheme.lower() == b"bearer"
            and hmac.compare_digest(supplied_token, configured_token.encode("utf-8"))
        )
        if not valid:
            await _json_response(send, 401, {"error": "invalid bearer token"})
            return
        await self.inner_app(scope, receive, send)


app = BearerTokenMiddleware(_mcp_http_app)


def main() -> None:
    """Run the local stdio MCP server."""

    mcp.run(transport="stdio")


def main_http() -> None:
    """Run the authenticated Streamable HTTP server."""

    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
