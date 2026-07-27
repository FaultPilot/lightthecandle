#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import configparser
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
APACHE_2_LICENSE_SHA256 = (
    "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"(?:postgres|postgresql)://[^:\s/]+:[^@\s/]+@", re.IGNORECASE),
)
PRIVATE_PATH = re.compile(r"/Users/[A-Za-z0-9._-]+/")
PUBLIC_PLACEHOLDER = re.compile(
    r"<" r"owner>|\[" r"TODO:|v" r"NEXT",
    re.IGNORECASE,
)
SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
REQUIRED_FILES = (
    "README.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "SUPPORT.md",
    "PRIVACY.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "MANIFEST.in",
    "release-artifacts.json",
    "docs/public-beta.md",
    "docs/release-checklist.md",
)


def candidate_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return [
        ROOT / value.decode("utf-8")
        for value in result.stdout.split(b"\0")
        if value
    ]


def base_versions() -> dict[str, str]:
    codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    setup = configparser.ConfigParser()
    setup.read(ROOT / "setup.cfg", encoding="utf-8")
    runtime_source = (ROOT / "src/lightthecandle/__init__.py").read_text(
        encoding="utf-8"
    )
    runtime_version: str | None = None
    for node in ast.parse(runtime_source).body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            runtime_version = node.value.value
            break
    if runtime_version is None:
        raise ValueError("Python runtime version assignment is missing or invalid")
    return {
        "codex": str(codex["version"]),
        "claude": str(claude["version"]),
        "python_metadata": setup["metadata"]["version"],
        "python_runtime": runtime_version,
    }


def scan_reachable_history() -> list[str]:
    try:
        objects = subprocess.run(
            ["git", "rev-list", "--objects", "--all"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        inventory = subprocess.run(
            [
                "git",
                "cat-file",
                "--batch-check=%(objectname) %(objecttype) %(objectsize) %(rest)",
            ],
            cwd=ROOT,
            input=objects.stdout,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        return [f"reachable Git history cannot be inspected: {error}"]

    issues: list[str] = []
    scanned: set[str] = set()
    for raw_line in inventory.stdout.splitlines():
        parts = raw_line.decode("utf-8", errors="replace").split(" ", 3)
        if len(parts) < 3 or parts[1] != "blob" or parts[0] in scanned:
            continue
        object_id, _, raw_size = parts[:3]
        scanned.add(object_id)
        try:
            size = int(raw_size)
        except ValueError:
            continue
        if size > 5 * 1024 * 1024:
            issues.append(f"reachable history blob requires manual review: {object_id}")
            continue
        try:
            blob = subprocess.run(
                ["git", "cat-file", "blob", object_id],
                cwd=ROOT,
                capture_output=True,
                check=True,
            ).stdout.decode("utf-8", errors="replace")
        except subprocess.CalledProcessError as error:
            issues.append(f"reachable history blob cannot be inspected: {object_id}: {error}")
            continue
        if any(pattern.search(blob) for pattern in SECRET_PATTERNS):
            relative = parts[3] if len(parts) == 4 else "(path unavailable)"
            issues.append(
                f"credential-like value found in reachable history: "
                f"{object_id[:12]} {relative}"
            )
    return issues


def release_state_issues(version: str) -> list[str]:
    issues: list[str] = []
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    if status.stdout.strip():
        issues.append("release worktree must be clean")

    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    normalized_remote = remote.stdout.strip().lower().rstrip("/")
    if normalized_remote.endswith(".git"):
        normalized_remote = normalized_remote[:-4]
    canonical_remotes = {
        "https://github.com/faultpilot/lightthecandle",
        "git@github.com:faultpilot/lightthecandle",
        "ssh://git@github.com/faultpilot/lightthecandle",
    }
    if remote.returncode != 0 or normalized_remote not in canonical_remotes:
        issues.append("origin must be the canonical FaultPilot/lightthecandle repository")

    expected_tag = f"lightthecandle--v{version}"
    tags = subprocess.run(
        ["git", "tag", "--points-at", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    if expected_tag not in tags.stdout.splitlines():
        issues.append(f"release commit must carry tag {expected_tag}")
    return issues


def check_release(
    *,
    require_license: bool,
    scan_history: bool,
    require_release_state: bool,
) -> list[str]:
    issues: list[str] = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            issues.append(f"required file missing: {relative}")
    if require_license:
        license_path = ROOT / "LICENSE"
        if not license_path.is_file():
            issues.append("publication requires an approved LICENSE")
        elif hashlib.sha256(license_path.read_bytes()).hexdigest() != APACHE_2_LICENSE_SHA256:
            issues.append("LICENSE does not match the approved Apache-2.0 text")
        if setup_license_metadata() != "Apache-2.0":
            issues.append("publication package metadata must declare Apache-2.0")
        setup = setup_metadata()
        expected_metadata = {
            "author": "Aaron Robbins",
            "author_email": "aaron@faultpilot.com.au",
            "url": "https://github.com/FaultPilot/lightthecandle",
        }
        for field, expected in expected_metadata.items():
            if setup.get(field) != expected:
                issues.append(
                    f"publication package metadata {field} must be {expected}"
                )

    versions = base_versions()
    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        issues.append(f"release versions differ: {versions}")
    version = versions["python_runtime"]
    if not SEMVER.fullmatch(version):
        issues.append(f"runtime version is not valid base Semantic Versioning: {version}")
    if f"Light the Candle v{version}" not in (ROOT / "README.md").read_text(encoding="utf-8"):
        issues.append("README version does not match runtime version")
    if f"## [{version}]" not in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"):
        issues.append("CHANGELOG has no section for the runtime version")
    artifact_allowlist = json.loads(
        (ROOT / "release-artifacts.json").read_text(encoding="utf-8")
    )
    if artifact_allowlist.get("sdist_root") != f"lightthecandle-{version}":
        issues.append("artifact allowlist source root does not match runtime version")
    if (
        artifact_allowlist.get("wheel_dist_info")
        != f"lightthecandle-{version}.dist-info"
    ):
        issues.append("artifact allowlist wheel metadata root does not match runtime version")

    for path in candidate_files():
        relative = path.relative_to(ROOT)
        if path.is_symlink():
            issues.append(f"tracked symlink requires explicit release review: {relative}")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if PRIVATE_PATH.search(content):
            issues.append(f"private absolute path found: {relative}")
        if PUBLIC_PLACEHOLDER.search(content):
            issues.append(f"public-release placeholder found: {relative}")
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                issues.append(f"credential-like value found: {relative}")
                break
        if path.suffix == ".json":
            try:
                json.loads(content)
            except json.JSONDecodeError as error:
                issues.append(f"invalid JSON in {relative}: {error}")
    if scan_history:
        issues.extend(scan_reachable_history())
    if require_release_state:
        issues.extend(release_state_issues(version))
    return issues


def setup_license_metadata() -> str | None:
    value = setup_metadata().get("license", "").strip()
    return value or None


def setup_metadata() -> configparser.SectionProxy:
    setup = configparser.ConfigParser()
    setup.read(ROOT / "setup.cfg", encoding="utf-8")
    return setup["metadata"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate public-release source state.")
    parser.add_argument(
        "--require-license",
        action="store_true",
        help="Fail unless an owner-approved LICENSE is present.",
    )
    parser.add_argument(
        "--scan-history",
        action="store_true",
        help="Scan every reachable Git blob for credential-like values.",
    )
    parser.add_argument(
        "--require-release-state",
        action="store_true",
        help="Require a clean canonical checkout tagged for the runtime version.",
    )
    args = parser.parse_args()
    issues = check_release(
        require_license=args.require_license,
        scan_history=args.scan_history,
        require_release_state=args.require_release_state,
    )
    payload = {
        "schema_version": "lightthecandle.release-guard/v1",
        "result": "blocked" if issues else "ok",
        "issues": issues,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
