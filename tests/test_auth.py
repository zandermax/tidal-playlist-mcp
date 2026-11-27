import datetime
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tidal_playlist_mcp import auth


@pytest.fixture
def store(tmp_path):
    return auth.SessionStore(tmp_path / "private" / "session.json")


@pytest.fixture
def credentials():
    return SimpleNamespace(
        token_type="Bearer",
        access_token="access-secret",
        refresh_token="refresh-secret",
        expiry_time=datetime.datetime(2030, 1, 1),
    )


def test_private_storage_and_missing_or_invalid_session(store, credentials):
    with pytest.raises(auth.SessionError, match="No saved session"):
        store.load()

    store.save(credentials)
    assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert store.path.parent.stat().st_uid == os.getuid()
    assert store.path.stat().st_uid == os.getuid()
    assert store.load() == ("Bearer", "access-secret", "refresh-secret", credentials.expiry_time)

    store.path.write_text('{"access_token": "secret"}')
    with pytest.raises(auth.SessionError, match="Invalid session"):
        store.load()


@pytest.mark.parametrize("target", ["directory", "file"])
def test_refuses_unsafe_modes_and_ownership(store, credentials, monkeypatch, target):
    store.save(credentials)
    path = store.path.parent if target == "directory" else store.path
    original_mode = stat.S_IMODE(path.stat().st_mode)
    path.chmod(original_mode | 0o040)
    with pytest.raises(auth.SessionError, match="unsafe"):
        store.load()
    path.chmod(original_mode)

    if target == "directory":
        monkeypatch.setattr(auth.os, "getuid", lambda: path.stat().st_uid + 1)
    else:
        original_fstat = auth.os.fstat

        def foreign_file_owner(fd):
            info = original_fstat(fd)
            if stat.S_ISREG(info.st_mode):
                fields = list(info)
                fields[4] = info.st_uid + 1
                return os.stat_result(fields)
            return info

        monkeypatch.setattr(auth.os, "fstat", foreign_file_owner)
    with pytest.raises(auth.SessionError, match="unsafe"):
        store.load()


def test_refuses_symlinks_and_nonregular_file(store, credentials, tmp_path):
    store.save(credentials)
    store.path.unlink()
    store.path.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(auth.SessionError, match="unsafe"):
        store.save(credentials)
    with pytest.raises(auth.SessionError, match="unsafe"):
        store.load()

    store.path.unlink()
    os.mkfifo(store.path, 0o600)
    with pytest.raises(auth.SessionError, match="unsafe"):
        store.load()
    store.path.unlink()
    store.path.parent.rmdir()
    real_dir = tmp_path / "actual"
    real_dir.mkdir(mode=0o700)
    store.path.parent.symlink_to(real_dir, target_is_directory=True)
    with pytest.raises(auth.SessionError, match="unsafe"):
        store.save(credentials)


def test_save_fails_on_permission_error_or_interrupted_replace(store, credentials, monkeypatch):
    store.save(credentials)
    original = store.path.read_bytes()

    with monkeypatch.context() as patch:
        def fail_fchmod(*args):
            raise PermissionError("denied")

        patch.setattr(auth.os, "fchmod", fail_fchmod)
        with pytest.raises(auth.SessionError, match="Cannot safely save"):
            store.save(credentials)
    assert store.path.read_bytes() == original
    assert list(store.path.parent.iterdir()) == [store.path]

    with monkeypatch.context() as patch:
        def fail_replace(*args, **kwargs):
            raise OSError("interrupted")

        patch.setattr(auth.os, "replace", fail_replace)
        credentials.access_token = "new-access"
        with pytest.raises(auth.SessionError, match="Cannot safely save"):
            store.save(credentials)
    assert store.path.read_bytes() == original
    assert list(store.path.parent.iterdir()) == [store.path]


def test_unsupported_platform_fails_explicitly(store, credentials, monkeypatch):
    monkeypatch.setattr(auth.sys, "platform", "unsupported")
    with pytest.raises(auth.SessionError, match="only on macOS"):
        store.save(credentials)


def test_rotated_refresh_token_is_persisted(store, credentials, monkeypatch, capsys):
    store.save(credentials)
    session = auth.PersistentSession(store)
    response = SimpleNamespace(
        ok=True,
        json=lambda: {
            "access_token": "new-access-secret",
            "refresh_token": "new-refresh-secret",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )
    monkeypatch.setattr(session.request_session, "post", lambda *args: response)
    assert session.token_refresh(credentials.refresh_token)
    assert store.load()[:3] == ("Bearer", "new-access-secret", "new-refresh-secret")
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize("valid", [True, False])
def test_loads_or_rejects_saved_oauth_session(store, credentials, monkeypatch, capsys, valid):
    store.save(credentials)
    received = []

    def fake_load(session, token_type, access_token, refresh_token, expiry_time):
        received.append((token_type, access_token, refresh_token, expiry_time))
        return valid

    monkeypatch.setattr(auth.PersistentSession, "load_oauth_session", fake_load)
    if valid:
        assert isinstance(auth.load_session(store), auth.PersistentSession)
    else:
        with pytest.raises(auth.SessionError, match="invalid"):
            auth.load_session(store)
    assert received == [("Bearer", "access-secret", "refresh-secret", credentials.expiry_time)]
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_terminal_login_displays_instructions_without_tokens(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    def fake_login(session):
        print("Visit https://example.test/authorize")
        session.token_type = "Bearer"
        session.access_token = "access-secret"
        session.refresh_token = "refresh-secret"
        session.expiry_time = datetime.datetime(2030, 1, 1)

    monkeypatch.setattr(auth.PersistentSession, "login_oauth_simple", fake_login)
    auth.login()
    captured = capsys.readouterr()
    assert "Visit https://example.test/authorize" in captured.out
    assert "access-secret" not in captured.out + captured.err
    assert "refresh-secret" not in captured.out + captured.err
    saved = tmp_path / ".config" / "tidal-playlist-mcp" / "session.json"
    assert json.loads(saved.read_text())["refresh_token"] == "refresh-secret"


def test_nonterminal_login_and_server_missing_session_do_not_prompt(tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    login = subprocess.run(
        [sys.executable, "-m", "tidal_playlist_mcp.auth"],
        input="", capture_output=True, text=True, env=env, timeout=10,
    )
    assert login.returncode != 0
    assert login.stdout == ""
    assert "interactive terminal" in login.stderr

    server = subprocess.run(
        [sys.executable, "-m", "tidal_playlist_mcp.server"],
        input="", capture_output=True, text=True, env=env, timeout=10,
    )
    assert server.returncode != 0
    assert server.stdout == ""
    assert "No saved session" in server.stderr

    directory = tmp_path / ".config" / "tidal-playlist-mcp"
    directory.mkdir(mode=0o700, parents=True)
    session_file = directory / "session.json"
    session_file.write_text('{"access_token": "access-secret"}')
    session_file.chmod(0o600)
    server = subprocess.run(
        [sys.executable, "-m", "tidal_playlist_mcp.server"],
        input="", capture_output=True, text=True, env=env, timeout=10,
    )
    assert server.returncode != 0
    assert server.stdout == ""
    assert "Invalid session" in server.stderr
    assert "access-secret" not in server.stderr
