from types import SimpleNamespace

import pytest

from tidal_playlist_mcp import inventory


class FakeRequest:
    def __init__(self, respond):
        self.respond = respond
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return SimpleNamespace(json=lambda: self.respond(path, kwargs["params"]))


def session(respond):
    return SimpleNamespace(
        user=SimpleNamespace(id=42),
        config=SimpleNamespace(api_v2_location="https://example.test/v2/"),
        request=FakeRequest(respond),
    )


def playlist_entry(number):
    return {
        "trn": f"trn:playlist:{number}",
        "data": {
            "uuid": str(number), "title": "same name", "creator": {"id": 42},
            "numberOfTracks": 2, "numberOfVideos": 1,
        },
    }


def media_entry(number, kind="track"):
    return {"type": kind, "item": {"id": number, "title": "song", "artists": [{"name": "artist"}]}}


def test_collection_pagination_and_nested_parent():
    first = [playlist_entry(i) for i in range(50)]
    folder = {"trn": "trn:folder:nested", "name": "Folder", "data": {"id": "nested"}}

    def respond(path, params):
        assert path == "my-collection/playlists/folders"
        assert params["folderId"] == "parent"
        if "cursor" not in params:
            return {"items": first, "cursor": "next", "totalNumberOfItems": 52}
        assert params["cursor"] == "next"
        return {"items": [playlist_entry(50), folder], "totalNumberOfItems": 52}

    result = inventory.list_collection(session(respond), "parent")
    assert result["complete"] is True
    assert len(result["items"]) == 52
    assert result["items"][0]["owned"] is True
    assert result["items"][-1] == {
        "type": "folder", "id": "nested", "name": "Folder", "parent_id": "parent",
    }


@pytest.mark.parametrize(
    "page",
    [
        {"items": [playlist_entry(1)], "cursor": "same"},
        {"items": [], "cursor": "new"},
        {"items": [playlist_entry(1)], "cursor": {"bad": "value"}},
        {"items": [playlist_entry(1)], "totalNumberOfItems": 2},
    ],
)
def test_collection_rejects_bad_continuations_or_inconsistent_total(page):
    client = session(lambda path, params: page)
    with pytest.raises(inventory.InventoryError):
        inventory.list_collection(client, cursor="same" if page.get("cursor") == "same" else None)


def test_collection_exposes_missing_continuation_and_page_bound():
    full_page = [playlist_entry(i) for i in range(50)]
    result = inventory.list_collection(session(lambda path, params: {"items": full_page}))
    assert result["complete"] is False
    assert result["next_cursor"] is None

    def respond(path, params):
        cursor = int(params.get("cursor", "0")) + 1
        return {"items": [playlist_entry(cursor)], "cursor": str(cursor)}

    result = inventory.list_collection(session(respond))
    assert result["complete"] is False
    assert result["next_cursor"] == "100"
    assert len(result["items"]) == 100


def test_playlist_metadata_and_items_across_pages():
    entries = [media_entry(i) for i in range(99)] + [media_entry(10, "VIDEO"), media_entry(10)]

    def respond(path, params):
        if path.endswith("/items"):
            offset = params["offset"]
            return {"items": entries[offset:offset + 100], "offset": offset, "totalNumberOfItems": len(entries)}
        return playlist_entry("abc")["data"]

    client = session(respond)
    assert inventory.get_playlist(client, "abc")["owned"] is True
    result = inventory.list_playlist_items(client, "abc")
    assert result["complete"] is True
    assert len(result["items"]) == 101
    assert [(item["position"], item["id"], item["type"]) for item in result["items"][-2:]] == [
        (99, "10", "video"), (100, "10", "track"),
    ]


@pytest.mark.parametrize("kind", ["ignored-offset", "repeated-page", "empty-page", "changing-total", "unknown-type"])
def test_playlist_rejects_incomplete_or_inconsistent_pages(kind):
    first = [media_entry(i) for i in range(100)]

    def respond(path, params):
        offset = params["offset"]
        if kind == "unknown-type":
            return {"items": [media_entry(1, "other")], "totalNumberOfItems": 1}
        if offset == 0:
            return {"items": first, "offset": 0, "totalNumberOfItems": 200}
        if kind == "ignored-offset":
            return {"items": first, "offset": 0, "totalNumberOfItems": 200}
        if kind == "repeated-page":
            return {"items": first, "offset": offset, "totalNumberOfItems": 200}
        if kind == "empty-page":
            return {"items": [], "offset": offset, "totalNumberOfItems": 200}
        return {"items": [media_entry(200)], "offset": offset, "totalNumberOfItems": 201}

    with pytest.raises(inventory.InventoryError):
        inventory.list_playlist_items(session(respond), "abc")


def test_api_errors_propagate():
    def fail(path, params):
        raise RuntimeError("upstream unavailable")

    with pytest.raises(RuntimeError, match="upstream unavailable"):
        inventory.list_collection(session(fail))
