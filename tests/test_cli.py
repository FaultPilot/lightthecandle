from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "ltc.py"
sys.path.insert(0, str(ROOT / "src"))

from lightthecandle import storage  # noqa: E402
from lightthecandle.model import (  # noqa: E402
    LightTheCandleError,
    load_policy,
    validate_manifest,
)


class LightTheCandleCliTest(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.project = self.root / "project"
        self.project.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(
        self,
        *args: str,
        cwd: Path | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        environment = {
            **os.environ,
            "LTC_HOME": str(self.home),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        environment.update(env_overrides or {})
        result = subprocess.run(
            [sys.executable, str(CLI), *args, "--json"],
            cwd=cwd or ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            self.fail(f"CLI did not return JSON: {result.stdout}\n{result.stderr}\n{error}")
        return result, payload

    def make_node_project(self, *, with_test: bool = True) -> None:
        scripts = {"dev": "next dev", "build": "next build"}
        if with_test:
            scripts["test"] = "vitest run"
        (self.project / "package.json").write_text(
            json.dumps(
                {
                    "name": "fixture-app",
                    "packageManager": "pnpm@10.0.0",
                    "scripts": scripts,
                    "dependencies": {"next": "15.0.0", "react": "19.0.0"},
                    "devDependencies": {"typescript": "5.0.0"},
                }
            ),
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "init", "-q", str(self.project)],
            text=True,
            capture_output=True,
            check=True,
        )

    def apply_adoption(
        self,
        *,
        profile: str = "quality",
        goal: str = "Help field teams complete safer work.",
        outcome: str = "Reduce incomplete field work.",
    ) -> dict:
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--profile",
            profile,
            "--goal",
            goal,
            "--outcome",
            outcome,
            "--apply",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "applied")
        return payload

    def test_profiles_are_structured_and_project_neutral(self) -> None:
        result, payload = self.run_cli("profiles")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            [profile["profile"] for profile in payload["profiles"]],
            ["prototype", "quality", "production", "enterprise"],
        )
        serialized = json.dumps(payload)
        self.assertNotIn("FaultPilot", serialized)
        self.assertNotIn("Supabase", serialized)

    def test_adopt_preview_is_read_only(self) -> None:
        self.make_node_project()
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--goal",
            "Ship a high-quality website.",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"], "preview")
        self.assertFalse((self.project / ".lightthecandle").exists())
        self.assertFalse(self.home.exists())
        self.assertEqual(payload["manifest"]["project_type"], "web")
        self.assertEqual(payload["manifest"]["commands"]["test"], ["pnpm", "run", "test"])

    def test_adopt_apply_creates_portable_manifest_and_chain(self) -> None:
        self.make_node_project()
        payload = self.apply_adoption()
        manifest_path = self.project / ".lightthecandle" / "project.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertNotIn(str(self.project), json.dumps(manifest))
        self.assertEqual(manifest["strategy"]["purpose"], "Help field teams complete safer work.")
        self.assertEqual(payload["event"]["previous_hash"], "")
        self.assertEqual(len(payload["event"]["hash"]), 64)

        db = self.home / "state.sqlite"
        before = hashlib.sha256(db.read_bytes()).hexdigest()
        state_before = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.home.glob("state.sqlite*")
        }
        status, status_payload = self.run_cli("status", str(self.project))
        after = hashlib.sha256(db.read_bytes()).hexdigest()
        state_after = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.home.glob("state.sqlite*")
        }
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(status_payload["ledger"]["event_count"], 1)
        self.assertTrue(status_payload["ledger"]["chain_valid"])
        self.assertEqual(after, before)
        self.assertEqual(state_after, state_before)

    def test_init_preview_does_not_create_new_directory(self) -> None:
        target = self.root / "new-app"
        result, payload = self.run_cli(
            "init",
            str(target),
            "--name",
            "New App",
            "--project-type",
            "mobile",
            "--profile",
            "prototype",
            "--goal",
            "Test a mobile workflow.",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["manifest"]["project_type"], "mobile")
        self.assertFalse(target.exists())
        self.assertFalse(self.home.exists())

    def test_init_apply_creates_only_namespaced_project_state(self) -> None:
        target = self.root / "new-app"
        result, payload = self.run_cli(
            "init",
            str(target),
            "--name",
            "New App",
            "--project-type",
            "mobile",
            "--profile",
            "prototype",
            "--goal",
            "Test a mobile workflow.",
            "--apply",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((target / ".lightthecandle" / "project.json").is_file())
        self.assertTrue((self.home / "state.sqlite").is_file())
        self.assertEqual(payload["manifest"]["quality_profile"], "prototype")

    def test_adopt_requires_real_project_markers(self) -> None:
        result, payload = self.run_cli("adopt", str(self.project))
        self.assertEqual(result.returncode, 10)
        self.assertEqual(payload["issues"][0]["code"], "PROJECT_NOT_DISCOVERED")
        self.assertFalse(self.home.exists())

    def test_existing_manifest_is_never_overwritten(self) -> None:
        self.make_node_project()
        self.apply_adoption()
        path = self.project / ".lightthecandle" / "project.json"
        before = path.read_bytes()
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--goal",
            "A different goal.",
            "--apply",
        )
        self.assertEqual(result.returncode, 10)
        self.assertEqual(payload["issues"][0]["code"], "PROJECT_ALREADY_ADOPTED")
        self.assertEqual(path.read_bytes(), before)

    def test_doctor_reports_profile_gaps_without_mutation(self) -> None:
        self.make_node_project(with_test=False)
        self.apply_adoption(profile="enterprise", goal="Run a critical customer platform.")
        manifest_path = self.project / ".lightthecandle" / "project.json"
        db_path = self.home / "state.sqlite"
        before = (manifest_path.read_bytes(), db_path.read_bytes())
        result, payload = self.run_cli("doctor", str(self.project))
        after = (manifest_path.read_bytes(), db_path.read_bytes())
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["result"], "attention")
        codes = {issue["code"] for issue in payload["issues"]}
        self.assertIn("REQUIRED_COMMAND_UNDISCOVERED", codes)
        self.assertIn("STRATEGY_FIELD_INCOMPLETE", codes)
        self.assertIn("CAPABILITY_UNDISCOVERED", codes)
        self.assertEqual(after, before)

    def test_doctor_blocks_secret_and_machine_path_in_manifest(self) -> None:
        self.make_node_project()
        self.apply_adoption()
        path = self.project / ".lightthecandle" / "project.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["strategy"]["api_token"] = "ghp_" + "123456789012345678901234"
        manifest["description"] = "/Users/" + "example/private/project"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        result, payload = self.run_cli("doctor", str(self.project))
        self.assertEqual(result.returncode, 10)
        codes = {issue["code"] for issue in payload["issues"]}
        self.assertIn("SECRET_FIELD_FORBIDDEN", codes)
        self.assertIn("SECRET_VALUE_FORBIDDEN", codes)
        self.assertIn("ABSOLUTE_PATH_FORBIDDEN", codes)

    def test_event_tampering_is_detected(self) -> None:
        self.make_node_project()
        self.apply_adoption()
        with sqlite3.connect(self.home / "state.sqlite") as connection:
            connection.execute(
                "UPDATE events SET payload_json='{}' WHERE sequence=1"
            )
        result, payload = self.run_cli("status", str(self.project))
        self.assertEqual(result.returncode, 10)
        self.assertFalse(payload["ledger"]["chain_valid"])
        self.assertIn(
            "EVENT_HASH_INVALID",
            {issue["code"] for issue in payload["issues"]},
        )

    def test_multiple_projects_each_start_event_sequence_at_one(self) -> None:
        self.make_node_project()
        first = self.apply_adoption()
        second_project = self.root / "second"
        second_project.mkdir()
        (second_project / "pyproject.toml").write_text(
            "[project]\nname='second'\nversion='0.1.0'\n",
            encoding="utf-8",
        )
        result, second = self.run_cli(
            "adopt",
            str(second_project),
            "--profile",
            "prototype",
            "--goal",
            "Publish a small Python library.",
            "--apply",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(first["event"]["sequence"], 1)
        self.assertEqual(second["event"]["sequence"], 1)
        status, payload = self.run_cli("status", str(second_project))
        self.assertEqual(status.returncode, 0)
        self.assertTrue(payload["ledger"]["chain_valid"])

    def test_copied_manifest_reports_unregistered_local_ledger(self) -> None:
        self.make_node_project()
        self.apply_adoption()
        for path in sorted(self.home.glob("state.sqlite*")):
            path.unlink()
        result, payload = self.run_cli("status", str(self.project))
        self.assertEqual(result.returncode, 0)
        self.assertIsNone(payload["ledger"]["chain_valid"])
        self.assertIn(
            "LOCAL_LEDGER_UNREGISTERED",
            {issue["code"] for issue in payload["issues"]},
        )
        doctor, doctor_payload = self.run_cli("doctor", str(self.project))
        self.assertEqual(doctor.returncode, 0)
        self.assertEqual(doctor_payload["result"], "attention")

    def test_symlinked_project_state_directory_cannot_redirect_write(self) -> None:
        self.make_node_project()
        outside = self.root / "outside"
        outside.mkdir()
        (self.project / ".lightthecandle").symlink_to(outside, target_is_directory=True)
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--goal",
            "Ship a safe project.",
            "--outcome",
            "Keep project state inside the repository.",
            "--apply",
        )
        self.assertEqual(result.returncode, 10)
        self.assertEqual(payload["issues"][0]["code"], "MANIFEST_PATH_UNSAFE")
        self.assertFalse((outside / "project.json").exists())

    def test_state_directory_swap_cannot_redirect_manifest_write(self) -> None:
        self.make_node_project()
        preview, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--goal",
            "Ship a safe project.",
            "--outcome",
            "Keep project state inside the repository.",
        )
        self.assertEqual(preview.returncode, 0, preview.stderr)
        state_directory = self.project / ".lightthecandle"
        state_directory.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        original_open = os.open
        swapped = False

        def swap_before_state_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if (
                not swapped
                and path == ".lightthecandle"
                and kwargs.get("dir_fd") is not None
            ):
                state_directory.rmdir()
                state_directory.symlink_to(outside, target_is_directory=True)
                swapped = True
            return original_open(path, flags, *args, **kwargs)

        with (
            mock.patch.dict(os.environ, {"LTC_HOME": str(self.home)}),
            mock.patch.object(storage.os, "open", side_effect=swap_before_state_open),
            self.assertRaises(LightTheCandleError) as context,
        ):
            storage.register_project(
                self.project,
                payload["manifest"],
                actor_id="race-test",
            )

        self.assertEqual(context.exception.code, "MANIFEST_PATH_UNSAFE")
        self.assertTrue(swapped)
        self.assertFalse((outside / "project.json").exists())

    def test_symlinked_ltc_home_cannot_redirect_ledger_write(self) -> None:
        self.make_node_project()
        outside = self.root / "outside-home"
        outside.mkdir()
        self.home.symlink_to(outside, target_is_directory=True)
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--profile",
            "prototype",
            "--goal",
            "Keep local state private.",
            "--apply",
        )
        self.assertEqual(result.returncode, 10)
        self.assertEqual(payload["issues"][0]["code"], "LTC_HOME_UNSAFE")
        self.assertFalse((outside / "state.sqlite").exists())

    @unittest.skipUnless(os.name == "posix", "POSIX permissions are required")
    def test_shared_ltc_home_is_rejected_without_chmod(self) -> None:
        self.make_node_project()
        self.home.mkdir(mode=0o755)
        self.home.chmod(0o755)
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--profile",
            "prototype",
            "--goal",
            "Keep local state private.",
            "--apply",
        )
        self.assertEqual(result.returncode, 10)
        self.assertEqual(payload["issues"][0]["code"], "LTC_HOME_UNSAFE")
        self.assertEqual(self.home.stat().st_mode & 0o777, 0o755)

    def test_symlinked_state_database_cannot_redirect_write(self) -> None:
        self.make_node_project()
        self.home.mkdir(mode=0o700)
        outside_database = self.root / "outside.sqlite"
        with sqlite3.connect(outside_database) as connection:
            connection.execute("CREATE TABLE sentinel(value TEXT)")
        before = hashlib.sha256(outside_database.read_bytes()).hexdigest()
        (self.home / "state.sqlite").symlink_to(outside_database)
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--profile",
            "prototype",
            "--goal",
            "Keep local state private.",
            "--apply",
        )
        self.assertEqual(result.returncode, 10)
        self.assertEqual(payload["issues"][0]["code"], "LEDGER_INVALID")
        self.assertEqual(hashlib.sha256(outside_database.read_bytes()).hexdigest(), before)
        self.assertFalse((self.project / ".lightthecandle" / "project.json").exists())

    def test_relative_ltc_home_is_rejected(self) -> None:
        self.make_node_project()
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--profile",
            "prototype",
            "--goal",
            "Keep local state unambiguous.",
            "--apply",
            env_overrides={"LTC_HOME": "relative-state"},
        )
        self.assertEqual(result.returncode, 10)
        self.assertEqual(payload["issues"][0]["code"], "LTC_HOME_UNSAFE")

    def test_ambient_git_paths_cannot_redirect_discovery(self) -> None:
        self.make_node_project()
        attacker = self.root / "attacker"
        attacker.mkdir()
        subprocess.run(
            ["git", "init", "-q", str(attacker)],
            text=True,
            capture_output=True,
            check=True,
        )
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--profile",
            "prototype",
            "--goal",
            "Adopt only the selected project.",
            env_overrides={
                "GIT_DIR": str(attacker / ".git"),
                "GIT_WORK_TREE": str(attacker),
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["project_root"], str(self.project.resolve()))
        self.assertFalse((attacker / ".lightthecandle").exists())

    def test_plain_folder_adoption_works_without_git_on_path(self) -> None:
        self.make_node_project()
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--profile",
            "prototype",
            "--goal",
            "Adopt a plain folder without Git.",
            env_overrides={"PATH": str(self.root / "empty-bin")},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["project_root"], str(self.project.resolve()))
        self.assertNotIn(
            "source_control",
            {
                adapter["capability"]
                for adapter in payload["manifest"]["adapters"]
            },
        )

    def test_http_basic_credentials_are_rejected_from_manifest(self) -> None:
        self.make_node_project()
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--goal",
            "Connect to https://alice:secret@example.com safely.",
        )
        self.assertEqual(result.returncode, 10)
        self.assertIn(
            "SECRET_VALUE_FORBIDDEN",
            {issue["code"] for issue in payload["issues"]},
        )

    def test_whitespace_strategy_values_block_local_registration(self) -> None:
        self.make_node_project()
        self.apply_adoption()
        for path in self.home.glob("state.sqlite*"):
            path.unlink()
        manifest_path = self.project / ".lightthecandle" / "project.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["strategy"]["outcomes"] = ["   "]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        result, payload = self.run_cli("register", str(self.project))
        self.assertEqual(result.returncode, 10)
        self.assertIn(
            "STRATEGY_FIELD_INVALID",
            {issue["code"] for issue in payload["issues"]},
        )

    def test_json_mode_covers_argument_errors(self) -> None:
        missing_command, missing_payload = self.run_cli()
        self.assertEqual(missing_command.returncode, 2)
        self.assertEqual(missing_payload["issues"][0]["code"], "ARGUMENT_INVALID")
        invalid_profile, invalid_payload = self.run_cli(
            "adopt",
            str(self.project),
            "--profile",
            "unsupported",
        )
        self.assertEqual(invalid_profile.returncode, 2)
        self.assertEqual(invalid_payload["command"], "adopt")
        self.assertEqual(invalid_payload["issues"][0]["code"], "ARGUMENT_INVALID")

    def test_unknown_manifest_fields_fail_closed(self) -> None:
        self.make_node_project()
        self.apply_adoption()
        path = self.project / ".lightthecandle" / "project.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["silent_policy_override"] = True
        path.write_text(json.dumps(manifest), encoding="utf-8")
        result, payload = self.run_cli("doctor", str(self.project))
        self.assertEqual(result.returncode, 10)
        self.assertIn(
            "MANIFEST_FIELDS_UNKNOWN",
            {issue["code"] for issue in payload["issues"]},
        )

    def test_corrupt_local_ledger_fails_closed(self) -> None:
        self.make_node_project()
        self.apply_adoption()
        database = self.home / "state.sqlite"
        database.write_bytes(b"not a sqlite database")
        result, payload = self.run_cli("status", str(self.project))
        self.assertEqual(result.returncode, 10)
        self.assertEqual(payload["issues"][0]["code"], "LEDGER_INVALID")

    def test_manifest_change_is_detected_against_registration(self) -> None:
        self.make_node_project()
        self.apply_adoption()
        path = self.project / ".lightthecandle" / "project.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["strategy"]["purpose"] = "An unexplained replacement purpose."
        path.write_text(json.dumps(manifest), encoding="utf-8")
        result, payload = self.run_cli("status", str(self.project))
        self.assertEqual(result.returncode, 10)
        self.assertFalse(payload["ledger"]["chain_valid"])
        self.assertIn(
            "MANIFEST_LEDGER_MISMATCH",
            {issue["code"] for issue in payload["issues"]},
        )

    def test_unknown_event_schema_fails_closed_even_with_valid_hash(self) -> None:
        self.make_node_project()
        self.apply_adoption()
        database = self.home / "state.sqlite"
        with sqlite3.connect(database) as connection:
            row = connection.execute(
                """
                SELECT sequence,event_id,project_id,event_type,recorded_at,actor_json,
                       payload_json,previous_hash
                FROM events WHERE sequence=1
                """
            ).fetchone()
            event = {
                "schema_version": "lightthecandle.event/v999",
                "sequence": row[0],
                "event_id": row[1],
                "project_id": row[2],
                "event_type": row[3],
                "recorded_at": row[4],
                "actor": json.loads(row[5]),
                "payload": json.loads(row[6]),
                "previous_hash": row[7],
            }
            digest = hashlib.sha256(
                json.dumps(
                    event,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ).encode("utf-8")
            ).hexdigest()
            connection.execute(
                "UPDATE events SET schema_version=?, hash=? WHERE sequence=1",
                (event["schema_version"], digest),
            )
        result, payload = self.run_cli("status", str(self.project))
        self.assertEqual(result.returncode, 10)
        self.assertIn(
            "EVENT_SCHEMA_UNSUPPORTED",
            {issue["code"] for issue in payload["issues"]},
        )

    def test_unregistered_manifest_can_be_registered_locally(self) -> None:
        self.make_node_project()
        self.apply_adoption()
        for path in self.home.glob("state.sqlite*"):
            path.unlink()
        preview, preview_payload = self.run_cli("register", str(self.project))
        self.assertEqual(preview.returncode, 0)
        self.assertEqual(preview_payload["result"], "preview")
        self.assertFalse(any(self.home.glob("state.sqlite*")))
        applied, applied_payload = self.run_cli(
            "register",
            str(self.project),
            "--reason",
            "Restored this trusted project copy on a new workstation.",
            "--apply",
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(applied_payload["event"]["event_type"], "project.registered_local")
        status, status_payload = self.run_cli("status", str(self.project))
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertTrue(status_payload["ledger"]["chain_valid"])

    def test_apply_requires_strategy_outcome_for_quality_profile(self) -> None:
        self.make_node_project()
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--goal",
            "Ship a quality project.",
            "--apply",
        )
        self.assertEqual(result.returncode, 10)
        self.assertEqual(payload["issues"][0]["code"], "OUTCOME_REQUIRED")
        self.assertFalse((self.project / ".lightthecandle").exists())

    def test_absolute_tmp_path_is_rejected_from_portable_manifest(self) -> None:
        self.make_node_project()
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--goal",
            "Ship a quality project.",
            "--outcome",
            "Store the project at /tmp/private-project.",
        )
        self.assertEqual(result.returncode, 10)
        self.assertIn(
            "ABSOLUTE_PATH_FORBIDDEN",
            {issue["code"] for issue in payload["issues"]},
        )

    def test_concurrent_adoption_never_overwrites_winning_manifest(self) -> None:
        self.make_node_project()
        previews = []
        for goal in ("First strategy.", "Second strategy."):
            result, payload = self.run_cli(
                "adopt",
                str(self.project),
                "--goal",
                goal,
                "--outcome",
                "Deliver one governed project record.",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            previews.append(payload["manifest"])

        barrier = threading.Barrier(2)
        original_create = storage.atomic_create_json
        successes: list[dict] = []
        failures: list[Exception] = []

        def synchronized_create(path: Path, value: dict) -> tuple[int, int]:
            barrier.wait(timeout=5)
            return original_create(path, value)

        def adopt(manifest: dict) -> None:
            try:
                successes.append(
                    storage.register_project(
                        self.project,
                        manifest,
                        actor_id="concurrency-test",
                    )
                )
            except Exception as error:
                failures.append(error)

        with (
            mock.patch.dict(os.environ, {"LTC_HOME": str(self.home)}),
            mock.patch.object(storage, "atomic_create_json", synchronized_create),
        ):
            threads = [
                threading.Thread(target=adopt, args=(manifest,))
                for manifest in previews
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], LightTheCandleError)
        self.assertEqual(failures[0].code, "PROJECT_ALREADY_ADOPTED")
        written = json.loads(
            (self.project / ".lightthecandle" / "project.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(written["project_id"], successes[0]["project_id"])
        status, payload = self.run_cli("status", str(self.project))
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertTrue(payload["ledger"]["chain_valid"])

    def test_runtime_manifest_validation_matches_portable_schema_constraints(self) -> None:
        self.make_node_project()
        result, payload = self.run_cli(
            "adopt",
            str(self.project),
            "--goal",
            "Ship a quality project.",
            "--outcome",
            "Produce a valid portable manifest.",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = payload["manifest"]
        manifest["name"] = ""
        manifest["created_at"] = "not-a-date"
        manifest["technologies"] = ["node", "node"]
        manifest["lifecycle"]["enabled_stages"].append(
            manifest["lifecycle"]["enabled_stages"][0]
        )
        codes = {issue["code"] for issue in validate_manifest(manifest)}
        self.assertIn("PROJECT_NAME_INVALID", codes)
        self.assertIn("CREATED_AT_INVALID", codes)
        self.assertIn("TECHNOLOGIES_INVALID", codes)
        self.assertIn("LIFECYCLE_STAGES_INVALID", codes)

    def test_malformed_packaged_policy_fails_with_structured_error(self) -> None:
        policy_root = self.root / "policy-package"
        policy_directory = policy_root / "policies"
        policy_directory.mkdir(parents=True)
        (policy_directory / "quality.json").write_text(
            json.dumps(
                {
                    "schema_version": "lightthecandle.policy/v1",
                    "profile": "quality",
                }
            ),
            encoding="utf-8",
        )
        with mock.patch(
            "lightthecandle.model.resources.files",
            return_value=policy_root,
        ):
            with self.assertRaises(LightTheCandleError) as context:
                load_policy("quality")
        self.assertEqual(context.exception.code, "POLICY_INVALID")


if __name__ == "__main__":
    unittest.main()
