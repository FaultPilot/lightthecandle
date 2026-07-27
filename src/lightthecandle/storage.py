from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Any
import uuid

from .model import EVENT_SCHEMA, LightTheCandleError, utc_now


MANIFEST_RELATIVE = Path(".lightthecandle/project.json")
GENESIS_EVENT_TYPES = {"project.adopted", "project.registered_local"}


def ltc_home() -> Path:
    value = os.environ.get("LTC_HOME")
    path = Path(value).expanduser() if value else (Path.home() / ".lightthecandle")
    if not path.is_absolute():
        raise LightTheCandleError(
            "LTC_HOME must be an absolute path.",
            code="LTC_HOME_UNSAFE",
            exit_code=10,
        )
    return Path(os.path.abspath(path))


def state_path() -> Path:
    return ltc_home() / "state.sqlite"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def atomic_create_json(path: Path, value: Any) -> tuple[int, int]:
    root = path.parents[1]
    state_name = path.parent.name
    temp_name = f".{path.name}.{uuid.uuid4().hex}"
    root_descriptor: int | None = None
    state_descriptor: int | None = None
    temp_descriptor: int | None = None
    final_created = False
    try:
        root_descriptor = os.open(root, _directory_flags())
        try:
            os.mkdir(state_name, mode=0o755, dir_fd=root_descriptor)
        except FileExistsError:
            pass
        state_descriptor = os.open(
            state_name,
            _directory_flags(),
            dir_fd=root_descriptor,
        )
        state_identity = os.fstat(state_descriptor)
        if not stat.S_ISDIR(state_identity.st_mode):
            raise LightTheCandleError(
                f"Project state path must be a directory: {path.parent}",
                code="MANIFEST_PATH_UNSAFE",
                exit_code=10,
            )
        live_state_identity = os.stat(
            state_name,
            dir_fd=root_descriptor,
            follow_symlinks=False,
        )
        if not _same_identity(state_identity, live_state_identity):
            raise LightTheCandleError(
                f"Project state directory changed during creation: {path.parent}",
                code="MANIFEST_PATH_UNSAFE",
                exit_code=10,
            )
        temp_descriptor = os.open(
            temp_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=state_descriptor,
        )
        with os.fdopen(temp_descriptor, "w", encoding="utf-8") as handle:
            temp_descriptor = None
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        try:
            os.link(
                temp_name,
                path.name,
                src_dir_fd=state_descriptor,
                dst_dir_fd=state_descriptor,
                follow_symlinks=False,
            )
            final_created = True
        except FileExistsError as error:
            raise LightTheCandleError(
                f"Refusing to overwrite existing manifest: {path}",
                code="PROJECT_ALREADY_ADOPTED",
                exit_code=10,
            ) from error
        live_state_identity = os.stat(
            state_name,
            dir_fd=root_descriptor,
            follow_symlinks=False,
        )
        if not _same_identity(state_identity, live_state_identity):
            raise LightTheCandleError(
                f"Project state directory changed during creation: {path.parent}",
                code="MANIFEST_PATH_UNSAFE",
                exit_code=10,
            )
        identity = os.stat(path.name, dir_fd=state_descriptor, follow_symlinks=False)
        os.unlink(temp_name, dir_fd=state_descriptor)
        return identity.st_dev, identity.st_ino
    except Exception as error:
        if state_descriptor is not None:
            if final_created:
                try:
                    os.unlink(path.name, dir_fd=state_descriptor)
                except FileNotFoundError:
                    pass
            try:
                os.unlink(temp_name, dir_fd=state_descriptor)
            except FileNotFoundError:
                pass
        if isinstance(error, OSError):
            raise LightTheCandleError(
                f"Project manifest path changed during creation: {error}",
                code="MANIFEST_PATH_UNSAFE",
                exit_code=10,
            ) from error
        raise
    finally:
        if temp_descriptor is not None:
            os.close(temp_descriptor)
        if state_descriptor is not None:
            os.close(state_descriptor)
        if root_descriptor is not None:
            os.close(root_descriptor)


def manifest_path(root: Path) -> Path:
    return root / MANIFEST_RELATIVE


def find_project_root(start: Path) -> Path:
    path = start.expanduser()
    if not path.exists():
        raise LightTheCandleError(
            f"Path does not exist: {path}",
            code="PROJECT_PATH_MISSING",
        )
    resolved = path.resolve(strict=True)
    if resolved.is_file():
        resolved = resolved.parent
    for candidate in (resolved, *resolved.parents):
        if manifest_path(candidate).is_file():
            return candidate
    raise LightTheCandleError(
        f"No .lightthecandle/project.json found from {resolved}",
        code="PROJECT_NOT_ADOPTED",
        exit_code=10,
    )


def read_manifest(root: Path) -> dict[str, Any]:
    path = manifest_path(root)
    if path.is_symlink():
        raise LightTheCandleError(
            f"Project manifest must not be a symlink: {path}",
            code="MANIFEST_PATH_UNSAFE",
            exit_code=10,
        )
    try:
        if path.exists() and not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
            raise LightTheCandleError(
                f"Project manifest escapes the project root: {path}",
                code="MANIFEST_PATH_UNSAFE",
                exit_code=10,
            )
    except OSError as error:
        raise LightTheCandleError(
            f"Project manifest path cannot be resolved safely: {error}",
            code="MANIFEST_PATH_UNSAFE",
            exit_code=10,
        ) from error
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise LightTheCandleError(
            f"Project manifest not found: {path}",
            code="PROJECT_NOT_ADOPTED",
            exit_code=10,
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise LightTheCandleError(
            f"Project manifest is unreadable: {error}",
            code="MANIFEST_INVALID",
            exit_code=10,
        ) from error
    if not isinstance(value, dict):
        raise LightTheCandleError(
            "Project manifest must contain a JSON object.",
            code="MANIFEST_INVALID",
            exit_code=10,
        )
    return value


def _state_path_error(message: str) -> LightTheCandleError:
    return LightTheCandleError(
        message,
        code="LTC_HOME_UNSAFE",
        exit_code=10,
    )


def _verify_private_state_home(path: Path) -> os.stat_result:
    try:
        identity = path.lstat()
    except OSError as error:
        raise _state_path_error(f"LTC_HOME cannot be inspected safely: {error}") from error
    if stat.S_ISLNK(identity.st_mode) or not stat.S_ISDIR(identity.st_mode):
        raise _state_path_error("LTC_HOME must be a real directory, not a symlink.")
    if os.name == "posix":
        if hasattr(os, "geteuid") and identity.st_uid != os.geteuid():
            raise _state_path_error("LTC_HOME must be owned by the current user.")
        if identity.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise _state_path_error("LTC_HOME permissions must not allow group or other access.")
    return identity


def _prepare_state_home(*, write: bool) -> Path | None:
    home = ltc_home()
    try:
        _verify_private_state_home(home)
        return home
    except LightTheCandleError:
        if home.exists() or home.is_symlink():
            raise
    if not write:
        return None
    try:
        home.mkdir(parents=True, mode=0o700, exist_ok=False)
    except FileExistsError:
        pass
    except OSError as error:
        raise _state_path_error(f"LTC_HOME cannot be created safely: {error}") from error
    _verify_private_state_home(home)
    return home


def _verify_private_state_file(path: Path) -> os.stat_result:
    try:
        identity = path.lstat()
    except OSError as error:
        raise LightTheCandleError(
            f"Local event ledger cannot be inspected safely: {error}",
            code="LEDGER_INVALID",
            exit_code=10,
        ) from error
    if stat.S_ISLNK(identity.st_mode) or not stat.S_ISREG(identity.st_mode):
        raise LightTheCandleError(
            "Local event ledger must be a real regular file, not a symlink.",
            code="LEDGER_INVALID",
            exit_code=10,
        )
    if os.name == "posix":
        if hasattr(os, "geteuid") and identity.st_uid != os.geteuid():
            raise LightTheCandleError(
                "Local event ledger must be owned by the current user.",
                code="LEDGER_INVALID",
                exit_code=10,
            )
        if identity.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise LightTheCandleError(
                "Local event ledger permissions must not allow group or other access.",
                code="LEDGER_INVALID",
                exit_code=10,
            )
    return identity


def _create_private_state_file(path: Path) -> os.stat_result:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path,
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        return os.fstat(descriptor)
    except FileExistsError:
        return _verify_private_state_file(path)
    except OSError as error:
        raise LightTheCandleError(
            f"Local event ledger cannot be created safely: {error}",
            code="LEDGER_INVALID",
            exit_code=10,
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def open_state(*, write: bool) -> sqlite3.Connection | None:
    home = _prepare_state_home(write=write)
    if home is None:
        return None
    path = home / "state.sqlite"
    if not write and not path.exists() and not path.is_symlink():
        return None
    expected_identity = (
        _create_private_state_file(path)
        if write
        else _verify_private_state_file(path)
    )
    if write:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(path, timeout=30, isolation_level=None)
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executescript(
                """
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                root TEXT NOT NULL UNIQUE,
                manifest_sha256 TEXT NOT NULL,
                registered_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence INTEGER NOT NULL,
                event_id TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                event_type TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                actor_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                hash TEXT NOT NULL UNIQUE,
                FOREIGN KEY(project_id) REFERENCES projects(project_id),
                UNIQUE(project_id, sequence)
            );
            CREATE INDEX IF NOT EXISTS events_project_sequence
                ON events(project_id, sequence);
            """
            )
            live_identity = _verify_private_state_file(path)
            if not _same_identity(expected_identity, live_identity):
                raise LightTheCandleError(
                    "Local event ledger changed while it was being opened.",
                    code="LEDGER_INVALID",
                    exit_code=10,
                )
        except sqlite3.Error as error:
            if connection is not None:
                connection.close()
            raise LightTheCandleError(
                f"Local event ledger cannot be opened for writing: {error}",
                code="LEDGER_INVALID",
                exit_code=10,
            ) from error
        except Exception:
            if connection is not None:
                connection.close()
            raise
        return connection
    uri = f"{path.as_uri()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
        live_identity = _verify_private_state_file(path)
        if not _same_identity(expected_identity, live_identity):
            connection.close()
            raise LightTheCandleError(
                "Local event ledger changed while it was being opened.",
                code="LEDGER_INVALID",
                exit_code=10,
            )
    except sqlite3.Error as error:
        raise LightTheCandleError(
            f"Local event ledger cannot be opened read-only: {error}",
            code="LEDGER_INVALID",
            exit_code=10,
        ) from error
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def event_hash(event: dict[str, Any]) -> str:
    content = {key: value for key, value in event.items() if key != "hash"}
    return sha256_json(content)


def validate_manifest_destination(root: Path) -> Path:
    path = manifest_path(root)
    state_directory = path.parent
    if state_directory.is_symlink():
        raise LightTheCandleError(
            f"Refusing to write through a symlinked state directory: {state_directory}",
            code="MANIFEST_PATH_UNSAFE",
            exit_code=10,
        )
    if path.exists() or path.is_symlink():
        raise LightTheCandleError(
            f"Refusing to overwrite existing manifest: {path}",
            code="PROJECT_ALREADY_ADOPTED",
            exit_code=10,
        )
    if state_directory.exists():
        try:
            if not state_directory.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
                raise LightTheCandleError(
                    f"State directory escapes the project root: {state_directory}",
                    code="MANIFEST_PATH_UNSAFE",
                    exit_code=10,
                )
        except OSError as error:
            raise LightTheCandleError(
                f"State directory cannot be resolved safely: {error}",
                code="MANIFEST_PATH_UNSAFE",
                exit_code=10,
            ) from error
    return path


def register_existing_project(
    root: Path,
    manifest: dict[str, Any],
    *,
    actor_id: str,
    event_type: str,
    reason: str | None = None,
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    connection = open_state(write=True)
    assert connection is not None
    manifest_sha = sha256_json(manifest)
    event: dict[str, Any] | None = None
    try:
        connection.execute("BEGIN IMMEDIATE")
        conflict = connection.execute(
            "SELECT project_id,root FROM projects WHERE project_id=? OR root=?",
            (manifest["project_id"], str(root)),
        ).fetchone()
        if conflict:
            raise LightTheCandleError(
                "Project identity or canonical path is already registered.",
                code="PROJECT_ALREADY_REGISTERED",
                exit_code=10,
            )
        connection.execute(
            "INSERT INTO projects(project_id,root,manifest_sha256,registered_at) VALUES(?,?,?,?)",
            (manifest["project_id"], str(root), manifest_sha, utc_now()),
        )
        recorded_at = utc_now()
        event = {
            "schema_version": EVENT_SCHEMA,
            "sequence": 1,
            "event_id": str(uuid.uuid4()),
            "project_id": manifest["project_id"],
            "event_type": event_type,
            "recorded_at": recorded_at,
            "actor": {"kind": "human", "id": actor_id},
            "payload": {
                "manifest_sha256": manifest_sha,
                "quality_profile": manifest["quality_profile"],
                "project_type": manifest["project_type"],
                "policy_sha256": manifest["policy"]["sha256"],
                "registration_reason": reason,
            },
            "previous_hash": "",
        }
        event["hash"] = event_hash(event)
        connection.execute(
            """
            INSERT INTO events(
                sequence,event_id,project_id,schema_version,event_type,recorded_at,
                actor_json,payload_json,previous_hash,hash
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event["sequence"],
                event["event_id"],
                event["project_id"],
                event["schema_version"],
                event["event_type"],
                event["recorded_at"],
                canonical_json(event["actor"]),
                canonical_json(event["payload"]),
                event["previous_hash"],
                event["hash"],
            ),
        )
        connection.execute("COMMIT")
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        connection.close()
    assert event is not None
    return event


def register_project(root: Path, manifest: dict[str, Any], *, actor_id: str) -> dict[str, Any]:
    path = validate_manifest_destination(root)
    manifest_sha = sha256_json(manifest)
    created_identity = atomic_create_json(path, manifest)
    try:
        return register_existing_project(
            root,
            manifest,
            actor_id=actor_id,
            event_type="project.adopted",
        )
    except Exception:
        try:
            identity = path.lstat()
            current = json.loads(path.read_text(encoding="utf-8"))
            if (
                not path.is_symlink()
                and (identity.st_dev, identity.st_ino) == created_identity
                and sha256_json(current) == manifest_sha
            ):
                path.unlink()
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            pass
        raise


def project_registration(project_id: str) -> dict[str, Any] | None:
    connection = open_state(write=False)
    if connection is None:
        return None
    try:
        row = connection.execute(
            "SELECT project_id,root,manifest_sha256,registered_at FROM projects WHERE project_id=?",
            (project_id,),
        ).fetchone()
    except sqlite3.Error as error:
        raise LightTheCandleError(
            f"Local project registry is unreadable: {error}",
            code="LEDGER_INVALID",
            exit_code=10,
        ) from error
    finally:
        connection.close()
    return dict(row) if row else None


def project_events(project_id: str) -> list[dict[str, Any]]:
    connection = open_state(write=False)
    if connection is None:
        return []
    try:
        rows = connection.execute(
            "SELECT * FROM events WHERE project_id=? ORDER BY sequence",
            (project_id,),
        ).fetchall()
    except sqlite3.Error as error:
        raise LightTheCandleError(
            f"Local event ledger is unreadable: {error}",
            code="LEDGER_INVALID",
            exit_code=10,
        ) from error
    finally:
        connection.close()
    events: list[dict[str, Any]] = []
    for row in rows:
        events.append(
            {
                "schema_version": row["schema_version"],
                "sequence": row["sequence"],
                "event_id": row["event_id"],
                "project_id": row["project_id"],
                "event_type": row["event_type"],
                "recorded_at": row["recorded_at"],
                "actor": json.loads(row["actor_json"]),
                "payload": json.loads(row["payload_json"]),
                "previous_hash": row["previous_hash"],
                "hash": row["hash"],
            }
        )
    return events


def verify_event_chain(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    previous_hash = ""
    project_id: str | None = None
    for expected_sequence, event in enumerate(events, start=1):
        event_id = str(event.get("event_id", "<unknown>"))
        if set(event) != {
            "schema_version",
            "sequence",
            "event_id",
            "project_id",
            "event_type",
            "recorded_at",
            "actor",
            "payload",
            "previous_hash",
            "hash",
        }:
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_FIELDS_INVALID",
                    "message": f"Event {event_id} has an invalid envelope.",
                }
            )
        if event.get("schema_version") != EVENT_SCHEMA:
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_SCHEMA_UNSUPPORTED",
                    "message": f"Event {event_id} uses an unsupported schema.",
                }
            )
        if event.get("sequence") != expected_sequence:
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_SEQUENCE_BROKEN",
                    "message": f"Expected event sequence {expected_sequence}.",
                }
            )
        try:
            uuid.UUID(event_id)
        except (ValueError, TypeError, AttributeError):
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_ID_INVALID",
                    "message": f"Event {event_id} does not have a UUID event_id.",
                }
            )
        current_project_id = str(event.get("project_id", ""))
        try:
            uuid.UUID(current_project_id)
        except (ValueError, TypeError, AttributeError):
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_PROJECT_ID_INVALID",
                    "message": f"Event {event_id} does not have a UUID project_id.",
                }
            )
        if project_id is None:
            project_id = current_project_id
        elif current_project_id != project_id:
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_PROJECT_CHANGED",
                    "message": f"Event {event_id} belongs to a different project.",
                }
            )
        if expected_sequence == 1 and event.get("event_type") not in GENESIS_EVENT_TYPES:
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_GENESIS_INVALID",
                    "message": "The first local event is not a supported registration event.",
                }
            )
        actor = event.get("actor")
        if (
            not isinstance(actor, dict)
            or set(actor) != {"kind", "id"}
            or actor.get("kind") not in {"human", "agent", "adapter", "system"}
            or not isinstance(actor.get("id"), str)
            or not actor.get("id")
        ):
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_ACTOR_INVALID",
                    "message": f"Event {event_id} has an invalid actor.",
                }
            )
        if not isinstance(event.get("payload"), dict):
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_PAYLOAD_INVALID",
                    "message": f"Event {event_id} has a non-object payload.",
                }
            )
        recorded_at = event.get("recorded_at")
        try:
            parsed_time = dt.datetime.fromisoformat(
                str(recorded_at).replace("Z", "+00:00")
            )
        except ValueError:
            parsed_time = None
        if (
            not isinstance(recorded_at, str)
            or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
                recorded_at,
            )
            or parsed_time is None
            or parsed_time.tzinfo is None
        ):
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_TIME_INVALID",
                    "message": f"Event {event_id} has an invalid timestamp.",
                }
            )
        current_previous_hash = event.get("previous_hash")
        if current_previous_hash != previous_hash:
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_CHAIN_BROKEN",
                    "message": f"Event {event_id} has the wrong previous hash.",
                }
            )
        current_hash = event.get("hash")
        if not isinstance(current_hash, str) or len(current_hash) != 64:
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_HASH_FORMAT_INVALID",
                    "message": f"Event {event_id} has an invalid hash format.",
                }
            )
        elif event_hash(event) != current_hash:
            issues.append(
                {
                    "severity": "error",
                    "code": "EVENT_HASH_INVALID",
                    "message": f"Event {event_id} does not match its hash.",
                }
            )
        previous_hash = current_hash if isinstance(current_hash, str) else ""
    return issues
