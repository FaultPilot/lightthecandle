from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any
import uuid

from .model import EVENT_SCHEMA, LightTheCandleError, utc_now


MANIFEST_RELATIVE = Path(".lightthecandle/project.json")
GENESIS_EVENT_TYPES = {"project.adopted", "project.registered_local"}


def ltc_home() -> Path:
    value = os.environ.get("LTC_HOME")
    return Path(value).expanduser().resolve() if value else (Path.home() / ".lightthecandle")


def state_path() -> Path:
    return ltc_home() / "state.sqlite"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def atomic_create_json(path: Path, value: Any) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o644)
        try:
            os.link(temp_path, path, follow_symlinks=False)
        except FileExistsError as error:
            raise LightTheCandleError(
                f"Refusing to overwrite existing manifest: {path}",
                code="PROJECT_ALREADY_ADOPTED",
                exit_code=10,
            ) from error
        identity = path.lstat()
        temp_path.unlink()
        return identity.st_dev, identity.st_ino
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


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


def open_state(*, write: bool) -> sqlite3.Connection | None:
    path = state_path()
    if not write and not path.exists():
        return None
    if write:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path.parent, 0o700)
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
            os.chmod(path, 0o600)
        except sqlite3.Error as error:
            raise LightTheCandleError(
                f"Local event ledger cannot be opened for writing: {error}",
                code="LEDGER_INVALID",
                exit_code=10,
            ) from error
        return connection
    uri = f"file:{path}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
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
