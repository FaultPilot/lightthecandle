from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent
RELEASE_GUARD = ROOT / "scripts" / "release_guard.py"


class ReleaseContractTest(unittest.TestCase):
    def test_release_source_guard_passes_without_legal_publication_gate(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RELEASE_GUARD)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, payload)
        self.assertEqual(payload["result"], "ok")

    def test_source_distribution_includes_runtime_policies(self) -> None:
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        for required_rule in (
            "recursive-include src/lightthecandle/policies *.json",
            "recursive-include docs *.md",
            "recursive-include schemas *.json",
            "recursive-include skills *.md *.yaml",
            "recursive-include tests *.py",
        ):
            self.assertIn(required_rule, manifest)

    def test_release_artifact_allowlist_covers_its_enforcement_files(self) -> None:
        allowlist = json.loads(
            (ROOT / "release-artifacts.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            allowlist["schema_version"],
            "lightthecandle.release-artifacts/v1",
        )
        self.assertEqual(allowlist["sdist_root"], "lightthecandle-0.1.3")
        self.assertEqual(
            allowlist["wheel_dist_info"],
            "lightthecandle-0.1.3.dist-info",
        )
        self.assertIn("release-artifacts.json", allowlist["sdist"])
        self.assertIn("LICENSE", allowlist["sdist"])
        self.assertIn("scripts/check_artifacts.py", allowlist["sdist"])
        self.assertIn(
            "lightthecandle-0.1.3.dist-info/LICENSE",
            allowlist["wheel"],
        )
        self.assertEqual(len(allowlist["sdist"]), len(set(allowlist["sdist"])))
        self.assertEqual(len(allowlist["wheel"]), len(set(allowlist["wheel"])))

    def test_project_schema_matches_runtime_lifecycle_and_command_rules(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "project.schema.json").read_text(encoding="utf-8")
        )
        commands = schema["properties"]["commands"]
        self.assertEqual(commands["propertyNames"]["pattern"], "\\S")
        lifecycle = schema["properties"]["lifecycle"]
        current_stages = set(
            lifecycle["properties"]["current_stage"]["enum"]
        )
        linked_stages = {
            rule["properties"]["current_stage"]["const"]
            for rule in lifecycle["oneOf"]
            if (
                rule["properties"]["enabled_stages"]["contains"]["const"]
                == rule["properties"]["current_stage"]["const"]
            )
        }
        self.assertEqual(linked_stages, current_stages)

    def test_publication_guard_enforces_owner_approved_license(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RELEASE_GUARD), "--require-license"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        if (ROOT / "LICENSE").is_file():
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["result"], "ok")
        else:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "publication requires an approved LICENSE",
                payload["issues"],
            )


if __name__ == "__main__":
    unittest.main()
