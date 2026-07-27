from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
import uuid

from . import __version__
from .discovery import discover, git_snapshot
from .model import (
    LIFECYCLE_STAGES,
    PROFILES,
    PROJECT_SCHEMA,
    PROJECT_TYPES,
    LightTheCandleError,
    load_policy,
    policy_digest,
    slugify,
    utc_now,
    validate_manifest,
)
from .storage import (
    find_project_root,
    manifest_path,
    project_events,
    project_registration,
    read_manifest,
    register_existing_project,
    register_project,
    sha256_json,
    validate_manifest_destination,
    verify_event_chain,
)


SECRET_KEY = re.compile(
    r"(?:^|_)(?:password|passwd|secret|token|api_?key|private_?key|credential)(?:$|_)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"(?:postgres|postgresql)://[^:\s/]+:[^@\s/]+@", re.IGNORECASE),
    re.compile(r"(?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S+", re.IGNORECASE),
)
ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9:/])(?:/(?!/)|~(?:/|\\)|[A-Za-z]:[\\/]|\\\\)"
)


def safe_actor_id(value: str | None) -> str:
    actor = value or os.environ.get("USER") or "local-user"
    if (
        len(actor) > 128
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._@-]*", actor)
        or any(pattern.search(actor) for pattern in SECRET_VALUE_PATTERNS)
    ):
        raise LightTheCandleError(
            "Actor ID must be a short non-secret local identity.",
            code="ACTOR_ID_INVALID",
            exit_code=10,
        )
    return actor


def strategy_seed(
    goal: str,
    *,
    outcomes: list[str],
    success_measures: list[str],
    assumptions: list[str],
    constraints: list[str],
) -> dict[str, Any]:
    return {
        "purpose": goal.strip(),
        "outcomes": [value.strip() for value in outcomes if value.strip()],
        "success_measures": [value.strip() for value in success_measures if value.strip()],
        "assumptions": [value.strip() for value in assumptions if value.strip()],
        "constraints": [value.strip() for value in constraints if value.strip()],
        "decision_principles": [
            "Prefer evidence over confidence.",
            "Keep the human owner in authority.",
            "Choose the simplest reversible path that meets the approved outcome.",
        ],
        "review_triggers": [
            "The intended user or outcome changes.",
            "A material assumption is disproved.",
            "Risk, cost, delivery time, or operational burden changes materially.",
        ],
    }


def build_manifest(
    discovery: dict[str, Any],
    *,
    name: str,
    description: str,
    goal: str,
    profile: str,
    outcomes: list[str],
    success_measures: list[str],
    assumptions: list[str],
    constraints: list[str],
) -> dict[str, Any]:
    policy = load_policy(profile)
    return {
        "schema_version": PROJECT_SCHEMA,
        "project_id": str(uuid.uuid4()),
        "slug": slugify(name),
        "name": name.strip(),
        "description": description.strip(),
        "project_type": discovery["project_type"],
        "quality_profile": profile,
        "policy": {
            "schema_version": policy["schema_version"],
            "profile": profile,
            "sha256": policy_digest(policy),
        },
        "created_at": utc_now(),
        "strategy": strategy_seed(
            goal,
            outcomes=outcomes,
            success_measures=success_measures,
            assumptions=assumptions,
            constraints=constraints,
        ),
        "lifecycle": {
            "current_stage": "discovery",
            "enabled_stages": policy["required_stages"],
        },
        "commands": discovery["commands"],
        "technologies": discovery["technologies"],
        "adapters": discovery["adapters"],
    }


def inspect_sensitive_values(value: Any, path: str = "$") -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if SECRET_KEY.search(str(key)):
                issues.append(
                    {
                        "severity": "error",
                        "code": "SECRET_FIELD_FORBIDDEN",
                        "message": f"Portable manifest contains a secret-like field: {child_path}",
                    }
                )
            issues.extend(inspect_sensitive_values(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(inspect_sensitive_values(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if ABSOLUTE_PATH.search(value):
            issues.append(
                {
                    "severity": "error",
                    "code": "ABSOLUTE_PATH_FORBIDDEN",
                    "message": f"Portable manifest contains a machine-specific path at {path}.",
                }
            )
        if any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
            issues.append(
                {
                    "severity": "error",
                    "code": "SECRET_VALUE_FORBIDDEN",
                    "message": f"Portable manifest contains a credential-like value at {path}.",
                }
            )
    return issues


def adoption_command(args: argparse.Namespace, *, mode: str) -> tuple[dict[str, Any], int]:
    requested_path = Path(args.path)
    discovery = discover(
        requested_path,
        project_type=args.project_type,
        allow_missing=mode == "init",
    )
    root: Path = discovery["root"]
    if mode == "adopt" and not discovery["has_project_content"]:
        raise LightTheCandleError(
            "No supported project markers were found. Use init for a new project.",
            code="PROJECT_NOT_DISCOVERED",
            exit_code=10,
        )
    if mode == "init" and root.exists() and discovery["has_project_content"]:
        raise LightTheCandleError(
            "This path already contains a project. Use adopt instead.",
            code="EXISTING_PROJECT_REQUIRES_ADOPT",
            exit_code=10,
        )
    validate_manifest_destination(root)
    name = args.name or root.name
    manifest = build_manifest(
        discovery,
        name=name,
        description=args.description or "",
        goal=args.goal or "",
        profile=args.profile,
        outcomes=args.outcome or [],
        success_measures=args.success_measure or [],
        assumptions=args.assumption or [],
        constraints=args.constraint or [],
    )
    issues = validate_manifest(manifest) + inspect_sensitive_values(manifest)
    report: dict[str, Any] = {
        "schema_version": "lightthecandle.report/v1",
        "command": mode,
        "result": "preview",
        "write_applied": False,
        "project_root": str(root),
        "manifest_path": str(manifest_path(root)),
        "manifest": manifest,
        "discovery": {
            key: value for key, value in discovery.items() if key != "root"
        },
        "issues": issues,
        "next_actions": [
            f"Review the proposed {args.profile} profile and strategy seed.",
            f"Run the same command with --apply to create {manifest_path(root)}.",
        ],
    }
    if any(issue["severity"] == "error" for issue in issues):
        report["result"] = "blocked"
        return report, 10
    if not args.apply:
        return report, 0
    if not manifest["strategy"]["purpose"]:
        raise LightTheCandleError(
            "--apply requires a non-empty --goal so durable work begins from intent.",
            code="INTENT_REQUIRED",
            exit_code=10,
        )
    if args.profile != "prototype" and not manifest["strategy"]["outcomes"]:
        raise LightTheCandleError(
            f"--apply with the {args.profile} profile requires at least one --outcome.",
            code="OUTCOME_REQUIRED",
            exit_code=10,
        )
    if not root.exists():
        root.mkdir(parents=True, exist_ok=False)
    event = register_project(
        root,
        manifest,
        actor_id=safe_actor_id(args.actor),
    )
    report.update(
        {
            "result": "applied",
            "write_applied": True,
            "event": event,
            "next_actions": [
                f"Run lightthecandle doctor {root}",
                "Complete the strategy outcomes and success measures before planning delivery.",
            ],
        }
    )
    return report, 0


def ledger_findings(
    root: Path,
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    registration: dict[str, Any] | None,
) -> list[dict[str, str]]:
    issues = verify_event_chain(events)
    if registration is None:
        issues.append(
            {
                "severity": "warning",
                "code": "LOCAL_LEDGER_UNREGISTERED",
                "message": "This project copy has not been registered in the local lifecycle ledger.",
            }
        )
        return issues

    current_manifest_sha = sha256_json(manifest)
    if Path(str(registration["root"])).resolve() != root.resolve():
        issues.append(
            {
                "severity": "error",
                "code": "PROJECT_ROOT_MISMATCH",
                "message": "The project identity is registered to a different canonical local path.",
            }
        )
    if registration["manifest_sha256"] != current_manifest_sha:
        issues.append(
            {
                "severity": "error",
                "code": "MANIFEST_LEDGER_MISMATCH",
                "message": "The portable manifest differs from the version registered in the local ledger.",
            }
        )
    if not events:
        issues.append(
            {
                "severity": "error",
                "code": "LEDGER_GENESIS_MISSING",
                "message": "The project is registered locally but its genesis event is missing.",
            }
        )
    else:
        genesis_payload = events[0].get("payload")
        if (
            not isinstance(genesis_payload, dict)
            or genesis_payload.get("manifest_sha256") != registration["manifest_sha256"]
        ):
            issues.append(
                {
                    "severity": "error",
                    "code": "LEDGER_GENESIS_MISMATCH",
                    "message": "The genesis event does not bind the registered manifest.",
                }
            )
    return issues


def status_report(path: Path) -> dict[str, Any]:
    root = find_project_root(path)
    manifest = read_manifest(root)
    manifest_issues = validate_manifest(manifest)
    project_id = str(manifest.get("project_id", ""))
    registration = project_registration(project_id)
    events = project_events(project_id)
    ledger_issues = ledger_findings(root, manifest, events, registration)
    git_state = git_snapshot(root)
    issues = manifest_issues + ledger_issues
    errors = [item for item in issues if item["severity"] == "error"]
    warnings = [item for item in issues if item["severity"] == "warning"]
    lifecycle = manifest.get("lifecycle")
    strategy = manifest.get("strategy")
    return {
        "schema_version": "lightthecandle.report/v1",
        "command": "status",
        "result": "blocked" if errors else ("attention" if warnings else "ok"),
        "project": {
            "project_id": manifest.get("project_id"),
            "slug": manifest.get("slug"),
            "name": manifest.get("name"),
            "project_type": manifest.get("project_type"),
            "quality_profile": manifest.get("quality_profile"),
            "current_stage": lifecycle.get("current_stage") if isinstance(lifecycle, dict) else None,
            "purpose": strategy.get("purpose") if isinstance(strategy, dict) else None,
            "manifest_sha256": sha256_json(manifest),
        },
        "workspace": git_state,
        "ledger": {
            "event_count": len(events),
            "head_hash": events[-1]["hash"] if events else None,
            "chain_valid": (
                not any(item["severity"] == "error" for item in ledger_issues)
                if registration is not None and events
                else None
            ),
        },
        "issues": issues,
        "next_actions": [
            "Run lightthecandle doctor to check profile readiness.",
        ],
    }


def status_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    report = status_report(Path(args.path))
    return report, 10 if report["result"] == "blocked" else 0


def profile_findings(manifest: dict[str, Any]) -> list[dict[str, str]]:
    profile = str(manifest.get("quality_profile", ""))
    try:
        policy = load_policy(profile)
    except LightTheCandleError as error:
        return [{"severity": "error", "code": error.code, "message": str(error)}]
    findings: list[dict[str, str]] = []
    binding = manifest.get("policy") if isinstance(manifest.get("policy"), dict) else {}
    if binding.get("sha256") != policy_digest(policy):
        findings.append(
            {
                "severity": "error",
                "code": "POLICY_DIGEST_MISMATCH",
                "message": "Installed policy content differs from the version bound to this project.",
            }
        )
    commands = manifest.get("commands") if isinstance(manifest.get("commands"), dict) else {}
    for command in policy.get("required_commands", []):
        if command not in commands:
            findings.append(
                {
                    "severity": "warning",
                    "code": "REQUIRED_COMMAND_UNDISCOVERED",
                    "message": f"{profile} profile expects a registered {command} command.",
                }
            )
    for command in policy.get("recommended_commands", []):
        if command not in commands:
            findings.append(
                {
                    "severity": "info",
                    "code": "RECOMMENDED_COMMAND_UNDISCOVERED",
                    "message": f"Consider registering a {command} command for the {profile} profile.",
                }
            )
    strategy = manifest.get("strategy") if isinstance(manifest.get("strategy"), dict) else {}
    for field in policy.get("required_strategy_fields", []):
        value = strategy.get(field)
        if value == "" or value == [] or value is None:
            findings.append(
                {
                    "severity": "warning",
                    "code": "STRATEGY_FIELD_INCOMPLETE",
                    "message": f"{profile} profile needs strategy.{field} before delivery planning.",
                }
            )
    adapters = manifest.get("adapters") if isinstance(manifest.get("adapters"), list) else []
    for capability in policy.get("required_capabilities", []):
        matches = [
            adapter
            for adapter in adapters
            if isinstance(adapter, dict) and adapter.get("capability") == capability
        ]
        if not matches:
            findings.append(
                {
                    "severity": "warning",
                    "code": "CAPABILITY_UNDISCOVERED",
                    "message": f"{profile} profile expects a {capability} adapter.",
                }
            )
        elif all(adapter.get("mode") == "disabled" for adapter in matches):
            findings.append(
                {
                    "severity": "warning",
                    "code": "CAPABILITY_DISABLED",
                    "message": f"{capability} is discovered but has no enabled adapter.",
                }
            )
    return findings


def doctor_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = find_project_root(Path(args.path))
    manifest = read_manifest(root)
    project_id = str(manifest.get("project_id", ""))
    registration = project_registration(project_id)
    events = project_events(project_id)
    ledger_issues = ledger_findings(root, manifest, events, registration)
    issues = (
        validate_manifest(manifest)
        + inspect_sensitive_values(manifest)
        + ledger_issues
        + profile_findings(manifest)
    )
    errors = [issue for issue in issues if issue["severity"] == "error"]
    warnings = [issue for issue in issues if issue["severity"] == "warning"]
    result = "blocked" if errors else ("attention" if warnings else "healthy")
    report = {
        "schema_version": "lightthecandle.report/v1",
        "command": "doctor",
        "result": result,
        "project_root": str(root),
        "quality_profile": manifest.get("quality_profile"),
        "issues": issues,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "info": len([issue for issue in issues if issue["severity"] == "info"]),
        },
        "next_actions": [issue["message"] for issue in errors + warnings[:3]],
    }
    return report, 10 if errors else 0


def register_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    root = find_project_root(Path(args.path))
    manifest = read_manifest(root)
    project_id = str(manifest.get("project_id", ""))
    registration = project_registration(project_id)
    events = project_events(project_id)
    issues = validate_manifest(manifest) + inspect_sensitive_values(manifest)
    if registration is not None:
        issues += ledger_findings(root, manifest, events, registration)
    reason = (args.reason or "").strip()
    if reason:
        reason_issues = [
            issue
            for issue in inspect_sensitive_values({"registration_reason": reason})
            if issue["code"] != "SECRET_FIELD_FORBIDDEN"
        ]
        issues += reason_issues
    errors = [issue for issue in issues if issue["severity"] == "error"]
    report: dict[str, Any] = {
        "schema_version": "lightthecandle.report/v1",
        "command": "register",
        "result": "blocked" if errors else ("already_registered" if registration else "preview"),
        "write_applied": False,
        "project_root": str(root),
        "project_id": project_id,
        "manifest_sha256": sha256_json(manifest),
        "issues": issues,
        "next_actions": [],
    }
    if errors:
        return report, 10
    if registration is not None:
        report["next_actions"] = ["Run lightthecandle status to inspect current state."]
        return report, 0
    if not args.apply:
        report["next_actions"] = [
            "Review the manifest and run register with --reason and --apply on this machine."
        ]
        return report, 0
    if not reason or len(reason) > 500:
        raise LightTheCandleError(
            "--apply requires a concise --reason of 1 to 500 characters.",
            code="REGISTRATION_REASON_REQUIRED",
            exit_code=10,
        )
    event = register_existing_project(
        root,
        manifest,
        actor_id=safe_actor_id(args.actor),
        event_type="project.registered_local",
        reason=reason,
    )
    report.update(
        {
            "result": "applied",
            "write_applied": True,
            "event": event,
            "next_actions": [f"Run lightthecandle doctor {root}"],
        }
    )
    return report, 0


def profiles_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    return (
        {
            "schema_version": "lightthecandle.report/v1",
            "command": "profiles",
            "result": "ok",
            "profiles": [load_policy(profile) for profile in PROFILES],
        },
        0,
    )


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"Light the Candle: {report['command']}",
        f"Result: {report['result']}",
    ]
    project = report.get("project")
    if project:
        lines.extend(
            [
                f"Project: {project.get('name')} ({project.get('project_type')})",
                f"Profile: {project.get('quality_profile')}",
                f"Stage: {project.get('current_stage')}",
            ]
        )
    if report.get("manifest"):
        manifest = report["manifest"]
        lines.extend(
            [
                f"Project: {manifest['name']} ({manifest['project_type']})",
                f"Profile: {manifest['quality_profile']}",
                f"Manifest: {report['manifest_path']}",
            ]
        )
    issues = report.get("issues") or []
    if issues:
        lines.append("Issues:")
        lines.extend(
            f"- [{item['severity'].upper()}] {item['code']}: {item['message']}"
            for item in issues
        )
    actions = report.get("next_actions") or []
    if actions:
        lines.append("Next:")
        lines.extend(f"- {action}" for action in actions)
    return "\n".join(lines)


def emit(report: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print(render_text(report))


def add_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Emit structured JSON.")


def add_project_creation(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--name")
    parser.add_argument("--description")
    parser.add_argument("--goal")
    parser.add_argument("--outcome", action="append")
    parser.add_argument("--success-measure", action="append")
    parser.add_argument("--assumption", action="append")
    parser.add_argument("--constraint", action="append")
    parser.add_argument("--profile", choices=PROFILES, default="quality")
    parser.add_argument("--project-type", choices=PROJECT_TYPES)
    parser.add_argument("--actor")
    parser.add_argument("--apply", action="store_true")
    add_output(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lightthecandle",
        description="A local-first virtual executive and software engineering organisation.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="Preview or initialise a new project.")
    add_project_creation(init_parser)
    adopt_parser = subparsers.add_parser("adopt", help="Preview or adopt an existing project.")
    add_project_creation(adopt_parser)
    register_parser = subparsers.add_parser(
        "register",
        help="Preview or register an existing portable manifest on this machine.",
    )
    register_parser.add_argument("path", nargs="?", default=".")
    register_parser.add_argument("--reason")
    register_parser.add_argument("--actor")
    register_parser.add_argument("--apply", action="store_true")
    add_output(register_parser)
    status_parser = subparsers.add_parser("status", help="Read current project state.")
    status_parser.add_argument("path", nargs="?", default=".")
    add_output(status_parser)
    doctor_parser = subparsers.add_parser("doctor", help="Check manifest and profile readiness.")
    doctor_parser.add_argument("path", nargs="?", default=".")
    add_output(doctor_parser)
    profiles_parser = subparsers.add_parser("profiles", help="List selectable rigor profiles.")
    add_output(profiles_parser)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command in {"init", "adopt"}:
            report, exit_code = adoption_command(args, mode=args.command)
        elif args.command == "register":
            report, exit_code = register_command(args)
        elif args.command == "status":
            report, exit_code = status_command(args)
        elif args.command == "doctor":
            report, exit_code = doctor_command(args)
        elif args.command == "profiles":
            report, exit_code = profiles_command(args)
        else:
            raise LightTheCandleError("Unknown command.", code="COMMAND_UNKNOWN")
    except LightTheCandleError as error:
        report = {
            "schema_version": "lightthecandle.report/v1",
            "command": getattr(args, "command", "unknown"),
            "result": "blocked",
            "issues": [
                {
                    "severity": "error",
                    "code": error.code,
                    "message": str(error),
                }
            ],
            "next_actions": [],
        }
        exit_code = error.exit_code
    except (OSError, json.JSONDecodeError) as error:
        report = {
            "schema_version": "lightthecandle.report/v1",
            "command": getattr(args, "command", "unknown"),
            "result": "blocked",
            "issues": [
                {
                    "severity": "error",
                    "code": "IO_FAILURE",
                    "message": str(error),
                }
            ],
            "next_actions": [],
        }
        exit_code = 2
    emit(report, as_json=bool(getattr(args, "json", False)))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
