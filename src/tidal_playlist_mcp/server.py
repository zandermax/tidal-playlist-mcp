"""MCP server entry point."""

import sys

from mcp.server import MCPServer

from tidal_playlist_mcp.auth import PersistentSession, SessionError, load_session
from tidal_playlist_mcp import inventory

mcp = MCPServer("TIDAL Playlist MCP")
session: PersistentSession | None = None


def _session() -> PersistentSession:
    if session is None:
        raise SessionError("TIDAL session is not available; run the login command.")
    return session


@mcp.tool()
def list_collection(parent_id: str = "root", cursor: str | None = None) -> dict:
    """List immediate folders and playlists under a folder."""
    return inventory.list_collection(_session(), parent_id, cursor)


@mcp.tool()
def get_playlist(playlist_id: str) -> dict:
    """Get playlist metadata by ID."""
    return inventory.get_playlist(_session(), playlist_id)


@mcp.tool()
def list_playlist_items(playlist_id: str, offset: int = 0) -> dict:
    """List playlist tracks and videos in order."""
    return inventory.list_playlist_items(_session(), playlist_id, offset)


def main() -> None:
    global session
    try:
        session = load_session()
    except SessionError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
