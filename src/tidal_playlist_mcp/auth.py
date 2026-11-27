"""Terminal login and private TIDAL session storage."""

import datetime
import json
import os
import secrets
import stat
import sys
from pathlib import Path

import requests
import tidalapi


class SessionError(Exception):
    """A session cannot be safely loaded or saved."""


def _check_private(info: os.stat_result, directory: bool) -> None:
    expected_mode = 0o700 if directory else 0o600
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if (
        not expected_type(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != expected_mode
    ):
        raise SessionError("Session directory or file has unsafe ownership, type, or permissions.")


def _parse_credentials(data: object) -> tuple[str, str, str, datetime.datetime]:
    if not isinstance(data, dict):
        raise SessionError("Invalid session file; run the login command again.")
    token_type = data.get("token_type")
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    expiry = data.get("expiry_time")
    if not (
        isinstance(token_type, str) and token_type
        and isinstance(access_token, str) and access_token
        and isinstance(refresh_token, str) and refresh_token
        and isinstance(expiry, str) and expiry
    ):
        raise SessionError("Invalid session file; run the login command again.")
    try:
        expiry_time = datetime.datetime.fromisoformat(expiry)
    except ValueError:
        raise SessionError("Invalid session expiry; run the login command again.") from None
    if expiry_time.tzinfo is not None:
        raise SessionError("Invalid session expiry; run the login command again.")
    return token_type, access_token, refresh_token, expiry_time


class SessionStore:
    def __init__(self, path: Path | None = None):
        self.path = path or Path.home() / ".config" / "tidal-playlist-mcp" / "session.json"

    def _open_directory(self, create: bool) -> int:
        if sys.platform != "darwin":
            raise SessionError("Private session storage is currently supported only on macOS.")
        directory = self.path.parent
        try:
            created = False
            if create:
                directory.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                try:
                    directory.mkdir(mode=0o700)
                except FileExistsError:
                    pass
                else:
                    created = True
            info = directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise SessionError("Session directory has unsafe ownership or type.")
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            valid = False
            try:
                if created:
                    os.fchmod(fd, 0o700)
                _check_private(os.fstat(fd), directory=True)
                valid = True
            finally:
                if not valid:
                    os.close(fd)
            return fd
        except FileNotFoundError:
            raise SessionError("No saved session; run the login command.") from None
        except OSError:
            raise SessionError("Cannot safely access the session directory.") from None

    def _open_file(self, directory_fd: int) -> int:
        try:
            info = os.stat(self.path.name, dir_fd=directory_fd, follow_symlinks=False)
            _check_private(info, directory=False)
            fd = os.open(
                self.path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd
            )
            valid = False
            try:
                _check_private(os.fstat(fd), directory=False)
                valid = True
            finally:
                if not valid:
                    os.close(fd)
            return fd
        except FileNotFoundError:
            raise SessionError("No saved session; run the login command.") from None
        except OSError:
            raise SessionError("Cannot safely access the session file.") from None

    def load(self) -> tuple[str, str, str, datetime.datetime]:
        directory_fd = self._open_directory(create=False)
        try:
            fd = self._open_file(directory_fd)
            with os.fdopen(fd, "r", encoding="utf-8") as file:
                try:
                    return _parse_credentials(json.load(file))
                except (ValueError, UnicodeError):
                    raise SessionError("Invalid session file; run the login command again.") from None
                except OSError:
                    raise SessionError("Cannot read the session file.") from None
        finally:
            os.close(directory_fd)

    def save(self, session: tidalapi.Session) -> None:
        data = {
            "token_type": session.token_type,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expiry_time": session.expiry_time.isoformat() if session.expiry_time else None,
        }
        _parse_credentials(data)
        directory_fd = self._open_directory(create=True)
        temporary_name = f".session-{secrets.token_hex(16)}.tmp"
        created = False
        try:
            try:
                os.stat(self.path.name, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                existing = self._open_file(directory_fd)
                os.close(existing)
            fd = os.open(
                temporary_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600, dir_fd=directory_fd,
            )
            created = True
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                os.fchmod(file.fileno(), 0o600)
                _check_private(os.fstat(file.fileno()), directory=False)
                json.dump(data, file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_name, self.path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            created = False
        except OSError:
            raise SessionError("Cannot safely save the session; run the login command again.") from None
        finally:
            try:
                if created:
                    os.unlink(temporary_name, dir_fd=directory_fd)
            finally:
                os.close(directory_fd)


class PersistentSession(tidalapi.Session):
    def __init__(self, store: SessionStore):
        super().__init__()
        self.store = store

    def token_refresh(self, refresh_token: str) -> bool:
        params = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        try:
            response = self.request_session.post(self.config.api_oauth2_token, params)
            if not response.ok:
                raise SessionError("TIDAL token refresh failed; run the login command again.")
            data = response.json()
            expiry = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
            expiry += datetime.timedelta(seconds=data["expires_in"])
            credentials = {
                "token_type": data["token_type"],
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", refresh_token),
                "expiry_time": expiry.isoformat(),
            }
            token_type, access_token, new_refresh_token, expiry = _parse_credentials(credentials)
        except (requests.RequestException, ValueError, KeyError, TypeError, OverflowError):
            raise SessionError("TIDAL token refresh failed; run the login command again.") from None
        self.token_type = token_type
        self.access_token = access_token
        self.refresh_token = new_refresh_token
        self.expiry_time = expiry
        self.store.save(self)
        return True


def load_session(store: SessionStore | None = None) -> PersistentSession:
    store = store or SessionStore()
    token_type, access_token, refresh_token, expiry_time = store.load()
    session = PersistentSession(store)
    try:
        if not session.load_oauth_session(token_type, access_token, refresh_token, expiry_time):
            raise SessionError("TIDAL session is invalid; run the login command again.")
    except requests.RequestException:
        raise SessionError("Cannot verify the TIDAL session; try again or log in.") from None
    return session


def login() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SessionError("Login requires an interactive terminal.")
    store = SessionStore()
    directory_fd = store._open_directory(create=True)
    os.close(directory_fd)
    session = PersistentSession(store)
    try:
        session.login_oauth_simple()
    except (requests.RequestException, TimeoutError):
        raise SessionError("TIDAL login failed; please try again.") from None
    store.save(session)
    print("TIDAL session saved.")


def main() -> None:
    try:
        login()
    except SessionError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
