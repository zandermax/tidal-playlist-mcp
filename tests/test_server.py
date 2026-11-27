import asyncio
import json
import select
import subprocess
import sys
from types import SimpleNamespace

from mcp import Client
from mcp.server import MCPServer

from tidal_playlist_mcp import server


def test_sdk_initializes_and_discovers_tools_with_fake_backend():
    class FakeBackend:
        def list_names(self) -> list[str]:
            return ["test playlist"]

    backend = FakeBackend()
    mcp = MCPServer("test server")

    @mcp.tool()
    def fake_list_playlists() -> list[str]:
        return backend.list_names()

    async def exercise():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            assert "fake_list_playlists" in [tool.name for tool in tools.tools]
            result = await client.call_tool("fake_list_playlists", {})
            assert not result.is_error
            assert result.structured_content == {"result": ["test playlist"]}

    asyncio.run(exercise())


def test_stdio_initialization_and_tool_discovery_are_json_rpc():
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from tidal_playlist_mcp import server; server.load_session = lambda: None; server.main()",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdin is not None
    assert process.stdout is not None

    def send(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def receive():
        ready, _, _ = select.select([process.stdout], [], [], 10)
        assert ready, "Timed out waiting for an MCP response"
        line = process.stdout.readline()
        assert line, "Server exited without an MCP response"
        message = json.loads(line)
        assert message["jsonrpc"] == "2.0"
        return message

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0"},
                },
            }
        )
        response = receive()
        assert response["id"] == 1
        assert response["result"]["serverInfo"]["name"] == "TIDAL Playlist MCP"

        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        response = receive()
        assert response["id"] == 2
        assert {tool["name"] for tool in response["result"]["tools"]} == {
            "list_collection", "get_playlist", "list_playlist_items",
        }
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)

    assert process.returncode == 0
    for line in process.stdout:
        assert json.loads(line)["jsonrpc"] == "2.0"


def test_client_calls_inventory_tools_across_pages(monkeypatch):
    class FakeRequest:
        def request(self, method, path, **kwargs):
            params = kwargs["params"]
            if path == "my-collection/playlists/folders":
                number = 2 if params.get("cursor") else 1
                data = {
                    "items": [{
                        "trn": f"trn:playlist:{number}",
                        "data": {"uuid": str(number), "title": "playlist", "creator": {"id": 42}},
                    }],
                    "cursor": "next" if number == 1 else None,
                    "totalNumberOfItems": 2,
                }
            elif path.endswith("/items"):
                offset = params["offset"]
                numbers = range(offset, min(offset + 100, 101))
                data = {
                    "items": [{"type": "track", "item": {"id": n, "title": "song"}} for n in numbers],
                    "offset": offset,
                    "totalNumberOfItems": 101,
                }
            else:
                data = {"uuid": "1", "title": "playlist", "creator": {"id": 42}}
            return SimpleNamespace(json=lambda: data)

    monkeypatch.setattr(server, "session", SimpleNamespace(
        user=SimpleNamespace(id=42),
        config=SimpleNamespace(api_v2_location="https://example.test/v2/"),
        request=FakeRequest(),
    ))

    async def exercise():
        def result_data(result):
            assert not result.is_error
            assert len(result.content) == 1
            assert result.content[0].type == "text"
            return json.loads(result.content[0].text)

        async with Client(server.mcp) as client:
            collection = result_data(await client.call_tool("list_collection", {"parent_id": "root"}))
            assert [item["id"] for item in collection["items"]] == ["1", "2"]
            assert collection["complete"] is True

            playlist = result_data(await client.call_tool("get_playlist", {"playlist_id": "1"}))
            assert playlist["id"] == "1"
            assert playlist["owned"] is True

            items = result_data(await client.call_tool("list_playlist_items", {"playlist_id": "1"}))
            assert len(items["items"]) == 101
            assert items["items"][-1]["position"] == 100
            assert items["complete"] is True

    asyncio.run(exercise())
