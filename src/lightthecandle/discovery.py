from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .model import LightTheCandleError, PROJECT_TYPES


PROJECT_MARKERS = (
    ".git",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
    "Gemfile",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Package.swift",
)


def safe_file(root: Path, relative: str) -> Path | None:
    candidate = root / relative
    if not candidate.exists():
        return None
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        return None
    if not resolved.is_relative_to(root):
        return None
    return resolved


def read_json(root: Path, relative: str) -> dict[str, Any] | None:
    path = safe_file(root, relative)
    if path is None or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    command = [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        *args,
    ]
    try:
        return subprocess.run(
            command,
            cwd=root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as error:
        return subprocess.CompletedProcess(
            command,
            returncode=127,
            stdout="",
            stderr=str(error),
        )


def git_root(path: Path) -> Path | None:
    result = git(path, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return None
    try:
        return Path(result.stdout.strip()).resolve(strict=True)
    except OSError:
        return None


def choose_root(path: Path, *, allow_missing: bool = False) -> Path:
    expanded = path.expanduser()
    if not expanded.exists():
        if allow_missing:
            return expanded.resolve(strict=False)
        raise LightTheCandleError(
            f"Project path does not exist: {expanded}",
            code="PROJECT_PATH_MISSING",
        )
    resolved = expanded.resolve(strict=True)
    if not resolved.is_dir():
        raise LightTheCandleError(
            f"Project path is not a directory: {resolved}",
            code="PROJECT_PATH_INVALID",
        )
    return git_root(resolved) or resolved


def has_project_content(root: Path) -> bool:
    return any((root / marker).exists() for marker in PROJECT_MARKERS)


def package_commands(package: dict[str, Any] | None) -> dict[str, list[str]]:
    if not package:
        return {}
    scripts = package.get("scripts")
    if not isinstance(scripts, dict):
        return {}
    package_manager = "pnpm" if package.get("packageManager", "").startswith("pnpm@") else "npm"
    aliases = {
        "serve": ("dev", "start"),
        "build": ("build",),
        "test": ("test",),
        "lint": ("lint",),
        "typecheck": ("typecheck", "type-check", "check:types"),
        "e2e": ("e2e", "test:e2e", "e2e:smoke"),
        "security": ("security", "audit"),
    }
    commands: dict[str, list[str]] = {}
    for capability, candidates in aliases.items():
        script = next((name for name in candidates if isinstance(scripts.get(name), str)), None)
        if script:
            commands[capability] = [package_manager, "run", script]
    return commands


def detect_python_commands(root: Path) -> dict[str, list[str]]:
    commands: dict[str, list[str]] = {}
    if safe_file(root, "pytest.ini") or safe_file(root, "tests"):
        commands["test"] = ["python3", "-m", "pytest"]
    pyproject = safe_file(root, "pyproject.toml")
    if pyproject:
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        if "[tool.ruff" in text:
            commands["lint"] = ["python3", "-m", "ruff", "check", "."]
        if "[tool.mypy" in text:
            commands["typecheck"] = ["python3", "-m", "mypy", "."]
    return commands


def infer_type(root: Path, package: dict[str, Any] | None) -> str:
    dependencies: dict[str, Any] = {}
    if package:
        for key in ("dependencies", "devDependencies"):
            value = package.get(key)
            if isinstance(value, dict):
                dependencies.update(value)
    if safe_file(root, "pnpm-workspace.yaml") or safe_file(root, "turbo.json"):
        return "monorepo"
    if safe_file(root, "capacitor.config.ts") or safe_file(root, "capacitor.config.json"):
        return "mobile"
    if safe_file(root, "android") or safe_file(root, "ios"):
        if package or safe_file(root, "Package.swift"):
            return "mobile"
    if "electron" in dependencies or safe_file(root, "src-tauri"):
        return "desktop"
    if any(name in dependencies for name in ("next", "react", "vue", "svelte", "@angular/core")):
        return "web"
    if any(name in dependencies for name in ("express", "fastify", "hono", "koa")):
        return "api"
    if safe_file(root, "pyproject.toml"):
        text = (safe_file(root, "pyproject.toml") or root).read_text(
            encoding="utf-8", errors="replace"
        )
        if any(name in text for name in ("fastapi", "django", "flask", "litestar")):
            return "api"
        if "[project.scripts]" in text:
            return "cli"
        return "library"
    if safe_file(root, "Cargo.toml") or safe_file(root, "go.mod"):
        return "library"
    if safe_file(root, "Dockerfile") or safe_file(root, "terraform"):
        return "infrastructure"
    return "generic"


def technologies(root: Path, package: dict[str, Any] | None) -> list[str]:
    detected: set[str] = set()
    if package:
        detected.add("node")
        dependencies: dict[str, Any] = {}
        for key in ("dependencies", "devDependencies"):
            value = package.get(key)
            if isinstance(value, dict):
                dependencies.update(value)
        mapping = {
            "next": "nextjs",
            "react": "react",
            "vue": "vue",
            "svelte": "svelte",
            "@angular/core": "angular",
            "@capacitor/core": "capacitor",
            "typescript": "typescript",
        }
        for package_name, label in mapping.items():
            if package_name in dependencies:
                detected.add(label)
    markers = {
        "pyproject.toml": "python",
        "requirements.txt": "python",
        "go.mod": "go",
        "Cargo.toml": "rust",
        "Gemfile": "ruby",
        "pom.xml": "java",
        "build.gradle": "java",
        "build.gradle.kts": "kotlin",
        "Package.swift": "swift",
        "Dockerfile": "docker",
    }
    for marker, label in markers.items():
        if safe_file(root, marker):
            detected.add(label)
    return sorted(detected)


def git_snapshot(root: Path) -> dict[str, Any] | None:
    if git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        return None
    branch = git(root, "branch", "--show-current").stdout.strip()
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    dirty_paths = [line for line in status.stdout.splitlines() if line]
    remote = git(root, "remote", "get-url", "origin")
    return {
        "branch": branch or None,
        "head": head or None,
        "dirty_count": len(dirty_paths),
        "remote": sanitize_remote(remote.stdout.strip()) if remote.returncode == 0 else None,
    }


def sanitize_remote(value: str) -> str | None:
    if not value:
        return None
    if value.startswith("/") or value.startswith("file://"):
        return "local"
    if "://" in value:
        try:
            parsed = urlsplit(value)
            hostname = parsed.hostname
            if not hostname:
                return None
            port = f":{parsed.port}" if parsed.port else ""
        except ValueError:
            return None
        return urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path, "", ""))
    if "@" in value and ":" in value:
        _, host_path = value.rsplit("@", 1)
        return host_path.split("?", 1)[0].split("#", 1)[0]
    return value.split("?", 1)[0].split("#", 1)[0]


def adapters(root: Path, git_state: dict[str, Any] | None) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if git_state:
        found.append({"capability": "source_control", "provider": "git", "mode": "read_only"})
        remote = git_state.get("remote") or ""
        if "github.com" in remote:
            found.append(
                {"capability": "code_host", "provider": "github", "mode": "read_only"}
            )
        elif "gitlab.com" in remote:
            found.append(
                {"capability": "code_host", "provider": "gitlab", "mode": "read_only"}
            )
    if safe_file(root, ".github/workflows"):
        found.append({"capability": "ci", "provider": "github-actions", "mode": "read_only"})
    if safe_file(root, "vercel.json"):
        found.append({"capability": "deployment", "provider": "vercel", "mode": "disabled"})
    if safe_file(root, "supabase"):
        found.append({"capability": "database", "provider": "supabase", "mode": "disabled"})
    if safe_file(root, "capacitor.config.ts") or safe_file(root, "capacitor.config.json"):
        found.append(
            {"capability": "distribution", "provider": "mobile-stores", "mode": "disabled"}
        )
    return found


def discover(path: Path, *, project_type: str | None = None, allow_missing: bool = False) -> dict[str, Any]:
    root = choose_root(path, allow_missing=allow_missing)
    if not root.exists():
        return {
            "root": root,
            "project_type": project_type or "generic",
            "technologies": [],
            "commands": {},
            "adapters": [],
            "git": None,
            "has_project_content": False,
        }
    package = read_json(root, "package.json")
    commands = package_commands(package)
    for name, command in detect_python_commands(root).items():
        commands.setdefault(name, command)
    inferred = project_type or infer_type(root, package)
    if inferred not in PROJECT_TYPES:
        raise LightTheCandleError(
            f"Unknown project type: {inferred}",
            code="PROJECT_TYPE_INVALID",
        )
    git_state = git_snapshot(root)
    return {
        "root": root,
        "project_type": inferred,
        "technologies": technologies(root, package),
        "commands": commands,
        "adapters": adapters(root, git_state),
        "git": git_state,
        "has_project_content": has_project_content(root),
    }
