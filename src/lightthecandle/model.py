from __future__ import annotations

import datetime as dt
import hashlib
from importlib import resources
import json
import re
from typing import Any
import uuid


PROJECT_SCHEMA = "lightthecandle.project/v1"
EVENT_SCHEMA = "lightthecandle.event/v1"
POLICY_SCHEMA = "lightthecandle.policy/v1"

PROFILES = ("prototype", "quality", "production", "enterprise")
PROJECT_TYPES = (
    "web",
    "mobile",
    "api",
    "library",
    "cli",
    "desktop",
    "data",
    "infrastructure",
    "monorepo",
    "generic",
)
LIFECYCLE_STAGES = (
    "idea",
    "discovery",
    "feasibility",
    "requirements",
    "product_design",
    "architecture",
    "security_privacy_data",
    "planning",
    "implementation",
    "verification",
    "release",
    "deployment",
    "operations",
    "maintenance",
    "incident_response",
    "retrospective",
    "retirement",
)
STRATEGY_FIELDS = {
    "purpose",
    "outcomes",
    "success_measures",
    "assumptions",
    "constraints",
    "decision_principles",
    "review_triggers",
}
POLICY_AUTHORITY = {
    "strategy_change",
    "policy_change",
    "external_write",
    "publication",
    "release",
    "deployment",
    "spending",
    "production_action",
    "policy_reduction",
}
RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


class LightTheCandleError(RuntimeError):
    def __init__(self, message: str, *, code: str = "LTC_ERROR", exit_code: int = 2):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise LightTheCandleError(
            "Project name must contain at least one letter or number.",
            code="INVALID_PROJECT_NAME",
        )
    return slug


def load_policy(profile: str) -> dict[str, Any]:
    if profile not in PROFILES:
        raise LightTheCandleError(
            f"Unknown quality profile: {profile}",
            code="UNKNOWN_PROFILE",
        )
    try:
        policy_text = (
            resources.files("lightthecandle")
            .joinpath("policies", f"{profile}.json")
            .read_text(encoding="utf-8")
        )
        policy = json.loads(policy_text)
    except (OSError, json.JSONDecodeError) as error:
        raise LightTheCandleError(
            f"Cannot load policy profile {profile}: {error}",
            code="POLICY_INVALID",
        ) from error
    required = {
        "schema_version",
        "profile",
        "description",
        "required_commands",
        "recommended_commands",
        "required_strategy_fields",
        "required_stages",
        "human_authority",
    }
    if (
        not isinstance(policy, dict)
        or set(policy) - required - {"required_capabilities"}
        or required - set(policy)
        or policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("profile") != profile
        or not isinstance(policy.get("description"), str)
        or not policy["description"].strip()
    ):
        raise LightTheCandleError(
            f"Policy profile {profile} has an invalid envelope.",
            code="POLICY_INVALID",
        )
    list_fields = (
        "required_commands",
        "recommended_commands",
        "required_strategy_fields",
        "required_stages",
        "required_capabilities",
        "human_authority",
    )
    for field in list_fields:
        value = policy.get(field, [])
        if (
            not isinstance(value, list)
            or any(not isinstance(item, str) or not item for item in value)
            or len(value) != len(set(value))
        ):
            raise LightTheCandleError(
                f"Policy profile {profile} has an invalid {field} list.",
                code="POLICY_INVALID",
            )
    if (
        not policy["required_stages"]
        or any(stage not in LIFECYCLE_STAGES for stage in policy["required_stages"])
        or any(field not in STRATEGY_FIELDS for field in policy["required_strategy_fields"])
        or any(authority not in POLICY_AUTHORITY for authority in policy["human_authority"])
    ):
        raise LightTheCandleError(
            f"Policy profile {profile} contains an unsupported requirement.",
            code="POLICY_INVALID",
        )
    return policy


def policy_digest(policy: dict[str, Any]) -> str:
    canonical = json.dumps(
        policy,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    required = {
        "schema_version",
        "project_id",
        "slug",
        "name",
        "project_type",
        "quality_profile",
        "policy",
        "created_at",
        "strategy",
        "lifecycle",
        "commands",
        "technologies",
        "adapters",
    }
    missing = sorted(required - set(manifest))
    if missing:
        issues.append(
            {
                "severity": "error",
                "code": "MANIFEST_FIELDS_MISSING",
                "message": f"Missing manifest fields: {', '.join(missing)}",
            }
        )
        return issues
    unknown = sorted(set(manifest) - required - {"description"})
    if unknown:
        issues.append(
            {
                "severity": "error",
                "code": "MANIFEST_FIELDS_UNKNOWN",
                "message": f"Unknown manifest fields: {', '.join(unknown)}",
            }
        )
    if manifest["schema_version"] != PROJECT_SCHEMA:
        issues.append(
            {
                "severity": "error",
                "code": "SCHEMA_UNSUPPORTED",
                "message": f"Unsupported schema: {manifest['schema_version']}",
            }
        )
    try:
        uuid.UUID(str(manifest["project_id"]))
    except (ValueError, TypeError, AttributeError):
        issues.append(
            {
                "severity": "error",
                "code": "PROJECT_ID_INVALID",
                "message": "project_id must be a UUID.",
            }
        )
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(manifest["slug"])):
        issues.append(
            {
                "severity": "error",
                "code": "PROJECT_SLUG_INVALID",
                "message": "slug must be lowercase hyphen-case.",
            }
        )
    if not isinstance(manifest["name"], str) or not manifest["name"].strip():
        issues.append(
            {
                "severity": "error",
                "code": "PROJECT_NAME_INVALID",
                "message": "name must be a non-empty string.",
            }
        )
    if "description" in manifest and not isinstance(manifest["description"], str):
        issues.append(
            {
                "severity": "error",
                "code": "PROJECT_DESCRIPTION_INVALID",
                "message": "description must be a string.",
            }
        )
    created_at = manifest["created_at"]
    try:
        parsed_created_at = dt.datetime.fromisoformat(
            str(created_at).replace("Z", "+00:00")
        )
    except ValueError:
        parsed_created_at = None
    if (
        not isinstance(created_at, str)
        or not RFC3339.fullmatch(created_at)
        or parsed_created_at is None
        or parsed_created_at.tzinfo is None
    ):
        issues.append(
            {
                "severity": "error",
                "code": "CREATED_AT_INVALID",
                "message": "created_at must be an RFC 3339 timestamp with a timezone.",
            }
        )
    if manifest["project_type"] not in PROJECT_TYPES:
        issues.append(
            {
                "severity": "error",
                "code": "PROJECT_TYPE_INVALID",
                "message": f"Unknown project type: {manifest['project_type']}",
            }
        )
    if manifest["quality_profile"] not in PROFILES:
        issues.append(
            {
                "severity": "error",
                "code": "PROFILE_INVALID",
                "message": f"Unknown quality profile: {manifest['quality_profile']}",
            }
        )
    policy = manifest["policy"]
    if (
        not isinstance(policy, dict)
        or set(policy) != {"schema_version", "profile", "sha256"}
        or policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("profile") != manifest["quality_profile"]
        or not re.fullmatch(r"[a-f0-9]{64}", str(policy.get("sha256", "")))
    ):
        issues.append(
            {
                "severity": "error",
                "code": "POLICY_BINDING_INVALID",
                "message": "policy must bind the selected profile to an exact policy digest.",
            }
        )
    if not isinstance(manifest["strategy"], dict):
        issues.append(
            {
                "severity": "error",
                "code": "STRATEGY_INVALID",
                "message": "strategy must be an object.",
            }
        )
    else:
        required_strategy = STRATEGY_FIELDS
        missing_strategy = sorted(required_strategy - set(manifest["strategy"]))
        unknown_strategy = sorted(set(manifest["strategy"]) - required_strategy)
        if missing_strategy:
            issues.append(
                {
                    "severity": "error",
                    "code": "STRATEGY_FIELDS_MISSING",
                    "message": f"Missing strategy fields: {', '.join(missing_strategy)}",
                }
            )
        if unknown_strategy:
            issues.append(
                {
                    "severity": "error",
                    "code": "STRATEGY_FIELDS_UNKNOWN",
                    "message": f"Unknown strategy fields: {', '.join(unknown_strategy)}",
                }
            )
        for field in required_strategy:
            value = manifest["strategy"].get(field)
            if field == "purpose":
                if not isinstance(value, str):
                    issues.append(
                        {
                            "severity": "error",
                            "code": "STRATEGY_FIELD_INVALID",
                            "message": "strategy.purpose must be a string.",
                        }
                    )
            elif not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                issues.append(
                    {
                        "severity": "error",
                        "code": "STRATEGY_FIELD_INVALID",
                        "message": f"strategy.{field} must be an array of strings.",
                    }
                )
    lifecycle = manifest["lifecycle"]
    if not isinstance(lifecycle, dict):
        issues.append(
            {
                "severity": "error",
                "code": "LIFECYCLE_INVALID",
                "message": "lifecycle must be an object.",
            }
        )
    else:
        unknown_lifecycle = sorted(set(lifecycle) - {"current_stage", "enabled_stages"})
        if unknown_lifecycle:
            issues.append(
                {
                    "severity": "error",
                    "code": "LIFECYCLE_FIELDS_UNKNOWN",
                    "message": f"Unknown lifecycle fields: {', '.join(unknown_lifecycle)}",
                }
            )
        current_stage = lifecycle.get("current_stage")
        enabled_stages = lifecycle.get("enabled_stages")
        if current_stage not in LIFECYCLE_STAGES:
            issues.append(
                {
                    "severity": "error",
                    "code": "LIFECYCLE_STAGE_INVALID",
                    "message": f"Unknown current lifecycle stage: {current_stage}",
                }
            )
        if (
            not isinstance(enabled_stages, list)
            or not enabled_stages
            or any(stage not in LIFECYCLE_STAGES for stage in enabled_stages)
            or len(enabled_stages) != len(set(enabled_stages))
        ):
            issues.append(
                {
                    "severity": "error",
                    "code": "LIFECYCLE_STAGES_INVALID",
                    "message": "enabled_stages must contain known lifecycle stages.",
                }
            )
        elif current_stage not in enabled_stages:
            issues.append(
                {
                    "severity": "error",
                    "code": "CURRENT_STAGE_DISABLED",
                    "message": "current_stage must be present in enabled_stages.",
                }
            )
    if not isinstance(manifest["commands"], dict):
        issues.append(
            {
                "severity": "error",
                "code": "COMMANDS_INVALID",
                "message": "commands must be an object of argument arrays.",
            }
        )
    else:
        for name, command in manifest["commands"].items():
            if (
                not isinstance(name, str)
                or not isinstance(command, list)
                or not command
                or not all(isinstance(part, str) and part for part in command)
            ):
                issues.append(
                    {
                        "severity": "error",
                        "code": "COMMAND_INVALID",
                        "message": f"Command {name!r} must be a non-empty argument array.",
                    }
                )
    if (
        not isinstance(manifest["technologies"], list)
        or not all(isinstance(value, str) and value for value in manifest["technologies"])
        or len(manifest["technologies"]) != len(set(manifest["technologies"]))
    ):
        issues.append(
            {
                "severity": "error",
                "code": "TECHNOLOGIES_INVALID",
                "message": "technologies must be an array of non-empty strings.",
            }
        )
    if not isinstance(manifest["adapters"], list):
        issues.append(
            {
                "severity": "error",
                "code": "ADAPTERS_INVALID",
                "message": "adapters must be an array.",
            }
        )
    else:
        for adapter in manifest["adapters"]:
            if (
                not isinstance(adapter, dict)
                or not isinstance(adapter.get("capability"), str)
                or not adapter.get("capability")
                or not isinstance(adapter.get("provider"), str)
                or not adapter.get("provider")
                or adapter.get("mode") not in {"read_only", "disabled"}
            ):
                issues.append(
                    {
                        "severity": "error",
                        "code": "ADAPTER_INVALID",
                        "message": "Each adapter needs capability, provider, and a safe mode.",
                    }
                )
            elif set(adapter) != {"capability", "provider", "mode"}:
                issues.append(
                    {
                        "severity": "error",
                        "code": "ADAPTER_FIELDS_INVALID",
                        "message": "Adapter fields must be capability, provider, and mode only.",
                    }
                )
    return issues
