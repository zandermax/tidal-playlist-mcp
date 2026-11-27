# TIDAL Playlist MCP

A local, read-only MCP server for exploring TIDAL playlists and folders.
Playlist editing is planned but not yet available. It uses the unofficial
`tidalapi` library; service behavior may change.

## Install and log in

On macOS, with Python 3.11 or newer, from this repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m tidal_playlist_mcp.auth
```

Run the login command in an interactive terminal and follow its browser link.
Do not share that link or your tokens. The server never prompts on MCP stdin.
To log in again, run the same command.

The session is stored in `~/.config/tidal-playlist-mcp/session.json`, not in
the repository. The directory must be owned by you and mode `0700`; the file
must be a regular file owned by you and mode `0600`. Unsafe paths are refused.
Session storage currently supports macOS only. To remove local credentials,
delete that session file; this does not revoke the TIDAL authorization.

## VS Code

The workspace MCP configuration is in `.vscode/mcp.json`. It runs this
repository's `.venv/bin/tidal-playlist-mcp` executable:

```json
{
  "servers": {
    "tidal-playlists": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/tidal-playlist-mcp"
    }
  }
}
```

Start the server from VS Code's MCP controls and enable its tools in Copilot.
Log in separately before starting it.

## Read-only tools

- `list_collection(parent_id="root", cursor=null)` lists immediate folders and
  playlists. Use a folder ID as `parent_id` to inspect its children.
- `get_playlist(playlist_id)` returns metadata for a playlist.
- `list_playlist_items(playlist_id, offset=0)` lists tracks and videos in order,
  including repeated occurrences.

Listings follow up to 100 service pages per call. Check `complete`; if false,
use `next_cursor` or `next_offset` when supplied. A full collection page with
no verifiable continuation or total is explicitly incomplete. Errors and
inconsistent pagination are reported instead of silently truncating data.
Live nested-folder and pagination behavior has not yet been verified.
