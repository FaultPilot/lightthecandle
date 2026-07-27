#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST = ROOT / "release-artifacts.json"


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and not path.is_absolute()
        and ".." not in path.parts
        and path.as_posix() == name
    )


def _sdist_files(
    path: Path,
    *,
    expected_root: str,
) -> tuple[set[str], list[str]]:
    issues: list[str] = []
    files: set[str] = set()
    with tarfile.open(path, mode="r:gz") as archive:
        roots: set[str] = set()
        for member in archive.getmembers():
            if not _safe_member(member.name):
                issues.append(f"unsafe sdist path: {member.name}")
                continue
            parts = PurePosixPath(member.name).parts
            if parts:
                roots.add(parts[0])
            if member.isdir():
                continue
            if not member.isfile():
                issues.append(f"non-regular sdist member: {member.name}")
                continue
            if len(parts) < 2:
                issues.append(f"sdist file is outside its release root: {member.name}")
                continue
            relative = PurePosixPath(*parts[1:]).as_posix()
            if relative in files:
                issues.append(f"duplicate sdist file: {relative}")
            files.add(relative)
        if roots != {expected_root}:
            issues.append(
                f"sdist release root differs: expected {expected_root}, "
                f"found {sorted(roots)}"
            )
    return files, issues


def _wheel_files(path: Path) -> tuple[set[str], list[str]]:
    issues: list[str] = []
    files: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            if not _safe_member(member.filename):
                issues.append(f"unsafe wheel path: {member.filename}")
                continue
            mode = member.external_attr >> 16
            if mode and (mode & 0o170000) not in (0, 0o100000):
                issues.append(f"non-regular wheel member: {member.filename}")
                continue
            if member.filename in files:
                issues.append(f"duplicate wheel file: {member.filename}")
            files.add(member.filename)
    return files, issues


def _compare(kind: str, actual: set[str], expected: set[str]) -> list[str]:
    issues: list[str] = []
    for name in sorted(actual - expected):
        issues.append(f"unexpected {kind} file: {name}")
    for name in sorted(expected - actual):
        issues.append(f"missing {kind} file: {name}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare release archives with the reviewed file allowlist."
    )
    parser.add_argument("--sdist", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    args = parser.parse_args()

    allowlist = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    sdist_files, issues = _sdist_files(
        args.sdist,
        expected_root=allowlist["sdist_root"],
    )
    wheel_files, wheel_issues = _wheel_files(args.wheel)
    issues.extend(wheel_issues)
    issues.extend(_compare("sdist", sdist_files, set(allowlist["sdist"])))
    issues.extend(_compare("wheel", wheel_files, set(allowlist["wheel"])))

    payload = {
        "schema_version": "lightthecandle.artifact-check/v1",
        "result": "blocked" if issues else "ok",
        "issues": issues,
        "sdist_file_count": len(sdist_files),
        "wheel_file_count": len(wheel_files),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
