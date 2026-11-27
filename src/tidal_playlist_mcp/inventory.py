"""Read-only inventory of a TIDAL collection."""

from typing import Any
from urllib.parse import quote

import tidalapi


class InventoryError(Exception):
    """The service returned invalid or incomplete inventory data."""


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value):
        raise InventoryError(f"Invalid or missing {field} in TIDAL response.")
    return str(value)


def _request(session: tidalapi.Session, path: str, params: dict, v2: bool = False) -> dict:
    kwargs: dict[str, Any] = {"params": params}
    if v2:
        kwargs["base_url"] = session.config.api_v2_location
    result = session.request.request("GET", path, **kwargs).json()
    if not isinstance(result, dict):
        raise InventoryError("Invalid TIDAL response.")
    return result


def _playlist(data: dict, user_id: object) -> dict:
    creator = data.get("creator")
    creator_id = creator.get("id") if isinstance(creator, dict) else None
    return {
        "id": _identifier(data.get("uuid"), "playlist ID"),
        "name": data.get("title"),
        "description": data.get("description"),
        "creator_id": str(creator_id) if creator_id is not None else None,
        "owned": str(creator_id) == str(user_id) if creator_id is not None and user_id is not None else None,
        "track_count": data.get("numberOfTracks"),
        "video_count": data.get("numberOfVideos"),
        "last_updated": data.get("lastUpdated"),
        "public": data.get("publicPlaylist"),
    }


def list_collection(session: tidalapi.Session, parent_id: str = "root", cursor: str | None = None) -> dict:
    """List immediate child folders and playlists, following up to 100 cursor pages."""
    if not parent_id:
        raise ValueError("parent_id must not be empty.")
    if cursor is not None and not cursor:
        raise ValueError("cursor must not be empty.")
    items = []
    started_at_beginning = cursor is None
    seen = {cursor} if cursor else set()
    for _ in range(100):
        params: dict[str, Any] = {
            "folderId": parent_id, "limit": 50, "order": "NAME", "includeOnly": "",
        }
        if cursor:
            params["cursor"] = cursor
        data = _request(session, "my-collection/playlists/folders", params, v2=True)
        page = data.get("items")
        if not isinstance(page, list):
            raise InventoryError("TIDAL collection response has no valid items list.")
        if len(page) > 50:
            raise InventoryError("TIDAL collection page exceeds the requested limit.")
        for item in page:
            if not isinstance(item, dict) or not isinstance(item.get("data"), dict):
                raise InventoryError("Malformed TIDAL collection item.")
            entry = item["data"]
            trn = item.get("trn")
            if isinstance(trn, str) and trn.startswith("trn:folder:"):
                items.append({
                    "type": "folder",
                    "id": _identifier(entry.get("id"), "folder ID"),
                    "name": item.get("name"),
                    "parent_id": parent_id,
                })
            elif isinstance(trn, str) and trn.startswith("trn:playlist:"):
                user_id = session.user.id if session.user else None
                items.append({"type": "playlist", **_playlist(entry, user_id)})
            else:
                raise InventoryError("Unknown TIDAL collection item type.")
        next_cursor = data.get("cursor")
        if next_cursor is None or next_cursor == "":
            total = data.get("totalNumberOfItems")
            if started_at_beginning and isinstance(total, int) and not isinstance(total, bool) and total != len(items):
                raise InventoryError("TIDAL collection total does not match the returned items.")
            if len(page) == 50 and not (
                started_at_beginning and isinstance(total, int) and total == len(items)
            ):
                return {
                    "items": items, "complete": False, "next_cursor": None,
                    "reason": "A full page had no continuation or verifiable total.",
                }
            return {"items": items, "complete": True, "next_cursor": None}
        if not isinstance(next_cursor, str) or next_cursor in seen or not page:
            raise InventoryError("TIDAL returned a malformed or non-advancing collection cursor.")
        seen.add(next_cursor)
        cursor = next_cursor
    return {"items": items, "complete": False, "next_cursor": cursor}


def get_playlist(session: tidalapi.Session, playlist_id: str) -> dict:
    if not playlist_id:
        raise ValueError("playlist_id must not be empty.")
    data = _request(session, f"playlists/{quote(playlist_id, safe='')}", {})
    return _playlist(data, session.user.id if session.user else None)


def list_playlist_items(session: tidalapi.Session, playlist_id: str, offset: int = 0) -> dict:
    """List up to 100 pages of playlist items, preserving duplicates and order."""
    if not playlist_id or offset < 0:
        raise ValueError("A playlist ID and non-negative offset are required.")
    path = f"playlists/{quote(playlist_id, safe='')}/items"
    items = []
    previous_page = None
    expected_total = None
    for _ in range(100):
        data = _request(session, path, {"limit": 100, "offset": offset})
        page = data.get("items")
        total = data.get("totalNumberOfItems")
        response_offset = data.get("offset")
        if not isinstance(page, list) or not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise InventoryError("TIDAL playlist response lacks valid items or total.")
        if response_offset is not None and response_offset != offset:
            raise InventoryError("TIDAL ignored the requested playlist offset.")
        if len(page) > 100 or offset + len(page) > total:
            raise InventoryError("TIDAL returned inconsistent playlist pagination.")
        if expected_total is not None and total != expected_total:
            raise InventoryError("Playlist changed during pagination; retry.")
        expected_total = total
        if previous_page is not None and page and page == previous_page:
            raise InventoryError("Playlist pages repeat; pagination may not be advancing.")
        for index, wrapper in enumerate(page, start=offset):
            if not isinstance(wrapper, dict) or not isinstance(wrapper.get("item"), dict):
                raise InventoryError("Malformed playlist item.")
            media = wrapper["item"]
            media_type = wrapper.get("type")
            if media_type not in ("track", "video", "TRACK", "VIDEO"):
                raise InventoryError("Unknown playlist media type.")
            artists = media.get("artists")
            items.append({
                "position": index,
                "type": media_type.lower(),
                "id": _identifier(media.get("id"), "media ID"),
                "title": media.get("title"),
                "artists": [a.get("name") for a in artists if isinstance(a, dict)] if isinstance(artists, list) else [],
                "duration": media.get("duration"),
            })
        offset += len(page)
        if offset == total:
            return {"items": items, "complete": True, "next_offset": None, "total": total}
        if not page:
            raise InventoryError("TIDAL returned an empty page before the playlist ended.")
        previous_page = page
    return {"items": items, "complete": False, "next_offset": offset, "total": expected_total}
