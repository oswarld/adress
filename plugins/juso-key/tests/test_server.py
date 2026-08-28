import asyncio
import os

from mcp import Client

import juso_key.server as server
from juso_key.server import app, mcp, verify_korean_address


def test_mcp_exposes_one_read_only_tool():
    tools = asyncio.run(mcp.list_tools())
    assert [tool.name for tool in tools] == ["verify_korean_address"]
    tool = tools[0]
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.destructive_hint is False


def test_tool_fails_closed_without_api_key():
    previous = os.environ.pop("JUSO_API_KEY", None)
    previous_index = os.environ.pop("JUSO_BULK_INDEX", None)
    try:
        try:
            verify_korean_address("서울특별시 중구 세종대로 110")
        except RuntimeError as error:
            assert "JUSO_API_KEY" in str(error)
        else:
            raise AssertionError("expected missing-key failure")
    finally:
        if previous is not None:
            os.environ["JUSO_API_KEY"] = previous
        if previous_index is not None:
            os.environ["JUSO_BULK_INDEX"] = previous_index


def test_tool_prefers_local_bulk_index_without_api_key(monkeypatch, tmp_path):
    index_path = tmp_path / "juso.sqlite"
    index_path.touch()
    monkeypatch.setenv("JUSO_BULK_INDEX", str(index_path))
    monkeypatch.delenv("JUSO_API_KEY", raising=False)

    class FakeBulkClient:
        evidence_source = "Juso bulk dataset (주소DB full release)"

        def __init__(self, path):
            assert path == index_path

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(server, "BulkSearchClient", FakeBulkClient)
    monkeypatch.setattr(
        server,
        "verify_address_with_client",
        lambda address, client: {
            "query": address,
            "matchStatus": "confirmed",
            "assertable": True,
            "evidence": {"source": client.evidence_source},
        },
    )

    result = verify_korean_address("서울특별시 중구 세종대로 110")
    assert result["assertable"] is True
    assert result["evidence"]["source"] == "Juso bulk dataset (주소DB full release)"


def test_tool_is_callable_through_mcp_protocol(monkeypatch):
    monkeypatch.setenv("JUSO_API_KEY", "test-key")
    monkeypatch.setattr(
        server,
        "verify_live_address",
        lambda address, approval_key: {
            "query": address,
            "matchStatus": "unmatched",
            "assertable": False,
            "addressKey": None,
        },
    )

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "verify_korean_address",
                {"address": "없는 주소 999"},
            )

    result = asyncio.run(call_tool())
    assert result.is_error is False
    assert result.structured_content["assertable"] is False


def test_http_endpoint_requires_bearer_token(monkeypatch):
    monkeypatch.setenv("MCP_BEARER_TOKEN", "expected-token")
    sent = []

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"authorization", b"Bearer wrong-token")],
    }
    asyncio.run(app(scope, receive, send))
    assert sent[0]["status"] == 401
