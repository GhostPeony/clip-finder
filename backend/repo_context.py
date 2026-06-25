"""Helpers for caller-supplied repository context."""

from __future__ import annotations

from typing import Any

REPO_CONTEXT_VERSION = "caller-supplied-repo-context-v1"

RECOMMENDED_REPO_CONTEXT_FIELDS = {
    "source": "Where the repo context came from, such as agent-mcp, filesystem, github, or codex.",
    "repo": "Repository owner/name, local project name, or workspace label.",
    "branch": "Optional branch or worktree identifier inspected by the calling agent.",
    "files": "Relevant file paths the calling agent inspected.",
    "locations": "Compact path, symbol, route, or line anchors the agent inspected, such as backend/context.py:734 build_agent_brief.",
    "entrypoints": "Routes, jobs, scripts, pages, handlers, or commands that start the relevant workflow.",
    "modules": "Relevant modules, packages, services, or directories.",
    "symbols": "Relevant functions, classes, components, workflows, routes, tools, or test names the agent inspected.",
    "features": "Feature areas that could benefit from saved-video knowledge.",
    "dependencies": "Key frameworks, services, models, APIs, or libraries that shape the implementation.",
    "commands": "Verified dev, test, build, migration, or deploy commands the agent can run.",
    "tests": "Relevant test files, suites, evals, or verification gates.",
    "deployment": "Hosting, runtime, queue, worker, database, or infrastructure facts.",
    "active_changes": "Dirty worktree, branch, PR, or user changes the agent must preserve.",
    "constraints": "Architecture, deployment, product, security, or user constraints.",
    "open_questions": "Questions the agent still needs the user or repo to answer.",
}

LIST_FIELDS = {
    "active_changes",
    "commands",
    "constraints",
    "dependencies",
    "deployment",
    "entrypoints",
    "features",
    "files",
    "locations",
    "modules",
    "open_questions",
    "symbols",
    "tests",
}
STRING_FIELDS = {"source", "repo", "branch"}
MAX_LIST_ITEMS = 20
MAX_STRING_LENGTH = 240
FOUNDATIONAL_FIELDS = ("source", "repo", "features", "constraints")
REPO_MAP_FIELDS = ("files", "modules", "entrypoints", "symbols", "locations")
VERIFICATION_FIELDS = ("commands", "tests")
RUNTIME_FIELDS = ("dependencies", "deployment")


def repo_context_json_schema() -> dict:
    """Return the JSON Schema MCP clients should use for repo_context forms."""

    string_schema = {
        "type": "string",
        "maxLength": MAX_STRING_LENGTH,
    }
    list_or_string_schema = {
        "oneOf": [
            {
                "type": "array",
                "items": {"type": "string", "maxLength": MAX_STRING_LENGTH},
                "maxItems": MAX_LIST_ITEMS,
            },
            {"type": "string", "maxLength": MAX_STRING_LENGTH},
        ],
    }
    properties = {}
    for field, description in RECOMMENDED_REPO_CONTEXT_FIELDS.items():
        if field in STRING_FIELDS:
            properties[field] = {**string_schema, "description": description}
        else:
            properties[field] = {**list_or_string_schema, "description": description}

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Caller Supplied Repo Context",
        "type": "object",
        "description": (
            "Compact repository facts gathered by the calling agent through its own "
            "repo, filesystem, GitHub, or code-index MCP tools."
        ),
        "properties": properties,
        "additionalProperties": True,
        "recommended": ["source", "repo", "features", "constraints"],
        "maxProperties": 32,
        "examples": [
            {
                "source": "agent-mcp",
                "repo": "GhostPeony/open-model-gym",
                "files": ["backend/evals.py", "agents/harness.ts"],
                "locations": ["backend/evals.py:42 run_eval_suite"],
                "entrypoints": ["POST /api/evals/run"],
                "symbols": ["run_eval_suite", "AgentHarness"],
                "features": ["reward model experiments", "workflow evals"],
                "commands": ["python -m pytest tests/test_evals.py -q"],
                "tests": ["tests/test_evals.py"],
                "constraints": ["source context is read-only"],
            }
        ],
    }


def describe_repo_context_contract() -> dict:
    """Return a self-describing contract for repo_context payloads."""
    return {
        "version": REPO_CONTEXT_VERSION,
        "purpose": (
            "Agents should bring compact repo context from their own filesystem, GitHub, "
            "or code-index MCP tools instead of requiring a hosted GitHub connection first."
        ),
        "recommendedFields": RECOMMENDED_REPO_CONTEXT_FIELDS,
        "rules": [
            "Keep repo_context compact; pass references and constraints, not large file dumps.",
            "Treat repo_context as caller-supplied working context, not persisted source truth.",
            "Use files/modules/symbols/locations/features to describe where saved-video concepts may apply.",
            "Use constraints to preserve architecture, deployment, product, and security limits.",
            "Save durable user-specific takeaways separately with overlay tools.",
        ],
        "jsonSchema": repo_context_json_schema(),
        "normalization": {
            "stringFields": sorted(STRING_FIELDS),
            "listFields": sorted(LIST_FIELDS),
            "listFieldsAcceptSingleString": True,
            "maxListItems": MAX_LIST_ITEMS,
            "maxStringLength": MAX_STRING_LENGTH,
            "extraFields": "Preserved under normalized.extra, capped to 12 keys.",
        },
        "readinessLevels": {
            "missing": "No usable repo_context was provided.",
            "partial": "The payload is valid but missing foundational fields.",
            "brief_ready": (
                "Enough repo context is present for a repo-aware source report, spec, "
                "or product brief."
            ),
            "implementation_ready": (
                "Enough repo context is present for an implementation plan with "
                "verification and runtime constraints."
            ),
        },
        "example": {
            "source": "agent-mcp",
            "repo": "GhostPeony/open-model-gym",
            "branch": "feature/eval-harness",
            "files": ["backend/evals.py", "agents/harness.ts"],
            "locations": [
                "backend/evals.py:42 run_eval_suite",
                "agents/harness.ts:18 AgentHarness",
            ],
            "entrypoints": ["POST /api/evals/run", "agents/harness.ts"],
            "modules": ["evaluation harness", "agent runner"],
            "symbols": ["run_eval_suite", "AgentHarness"],
            "features": ["reward model experiments", "workflow evals"],
            "dependencies": ["Supabase", "OpenAI SDK"],
            "commands": ["npm test -- --run", "python -m pytest tests/test_evals.py -q"],
            "tests": ["tests/test_evals.py", "src/agents/harness.test.ts"],
            "deployment": ["Cloudflare container worker", "Supabase Postgres"],
            "active_changes": ["preserve existing agent runner refactor"],
            "constraints": ["Supabase remains the system of record", "source context is read-only"],
            "open_questions": ["Which eval metrics should gate release?"],
        },
    }


def repo_context_workflow_contract() -> dict:
    """Return machine-readable steps for caller-supplied repo context collection."""
    return {
        "preferred": "caller_supplied_repo_context",
        "reason": (
            "Lower friction: coding agents usually already have filesystem, GitHub, "
            "or repo-index MCP access."
        ),
        "contractResource": "context://repo-context-contract",
        "contractTool": "get_repo_context_contract",
        "collectionPrompt": "collect_repo_context",
        "validationTool": "validate_repo_context",
        "readinessField": "readiness",
        "readinessGate": {
            "minimumForBrief": "brief_ready",
            "preferredForImplementation": "implementation_ready",
            "retryWhen": ["missing", "partial"],
            "retryInstruction": (
                "Follow readiness.suggestedAgentNextSteps with the caller's repo tools, "
                "update repo_context, then call validate_repo_context again."
            ),
        },
        "readinessLevels": ["missing", "partial", "brief_ready", "implementation_ready"],
        "jsonSchema": repo_context_json_schema(),
        "schema": {
            "source": "agent-mcp",
            "repo": "owner/name or local project name",
            "branch": "optional branch or ref",
            "files": ["relevant/path.ts"],
            "locations": ["relevant/path.ts:123 symbol_or_route"],
            "entrypoints": ["route, worker, job, script, or UI entrypoint"],
            "modules": ["relevant module or service"],
            "symbols": ["relevant function, class, component, workflow, tool, or test"],
            "features": ["feature area that could use saved-video knowledge"],
            "dependencies": ["framework, service, model, API, or library"],
            "commands": ["verified test/build/dev command"],
            "tests": ["relevant test file, eval, or verification gate"],
            "deployment": ["runtime, queue, database, or hosting fact"],
            "active_changes": ["dirty worktree, branch, PR, or user change to preserve"],
            "constraints": ["architecture, deployment, product, or user constraint"],
            "open_questions": ["optional unresolved repo question"],
        },
        "collectPromptExpectedOutput": {
            "repo_context": "normalized repo_context returned by validate_repo_context",
            "readiness": {
                "level": "missing | partial | brief_ready | implementation_ready",
                "readyForBrief": "boolean",
                "readyForImplementationBrief": "boolean",
                "missingSignals": {
                    "foundational": ["missing source/repo/features/constraints fields"],
                    "repoMap": ["missing files/modules/entrypoints/symbols/locations signals"],
                    "verification": ["missing commands/tests signals"],
                    "runtime": ["missing dependencies/deployment signals"],
                    "changeSafety": ["missing active_changes when relevant"],
                },
                "suggestedAgentNextSteps": ["next repo-inspection actions, if any"],
            },
            "open_questions": ["questions still blocking safer implementation planning"],
            "next_mcp_call": {
                "name": "validate_repo_context | build_context_bundle | build_agent_brief",
                "when": "after_more_repo_inspection | for_brief | next",
                "reason": "why this is the recommended next MCP call",
                "argumentsTemplate": {"repo_context": "normalized or updated repo_context"},
            },
        },
        "steps": [
            "Inspect the repo with the calling agent's own repo/filesystem/GitHub tools.",
            "Use prompts/get collect_repo_context when the agent wants guided repo inspection before requesting video-derived implementation guidance.",
            "Build a compact repo_context object with repo, files, locations, entrypoints, symbols, dependencies, commands, tests, features, and constraints.",
            "Call validate_repo_context before implementation planning and follow readiness.suggestedAgentNextSteps when context is partial.",
            "Return collectPromptExpectedOutput after collect_repo_context so the caller can decide the next MCP call.",
            "Call build_agent_brief or build_context_bundle with query and repo_context.",
            "Cite returned source_refs when turning saved-video knowledge into specs or plans.",
            "Persist only durable user-specific takeaways with overlay tools.",
        ],
    }


def validate_repo_context(repo_context: Any) -> dict:
    """Normalize a repo_context payload and return warnings for agent callers."""
    if repo_context is None:
        normalized = {}
        warnings = ["repo_context was not provided."]
    elif not isinstance(repo_context, dict):
        normalized = {}
        warnings = ["repo_context must be an object."]
    else:
        normalized, warnings = _normalize_repo_context(repo_context)

    missing_recommended = [
        field
        for field in ("source", "repo", "features", "constraints")
        if not normalized.get(field)
    ]
    if missing_recommended:
        warnings.append("Missing recommended fields: " + ", ".join(missing_recommended) + ".")

    readiness = _repo_context_readiness(normalized, missing_recommended, warnings)
    next_mcp_call = _repo_context_next_mcp_call(readiness["level"])

    return {
        "valid": not any(warning.endswith("must be an object.") for warning in warnings),
        "normalized": normalized,
        "warnings": warnings,
        "missingRecommended": missing_recommended,
        "readiness": readiness,
        "next_mcp_call": next_mcp_call,
        "contract": describe_repo_context_contract(),
    }


def normalize_repo_context(repo_context: Any) -> dict:
    """Return the normalized repo_context object used in bundles and briefs."""
    return validate_repo_context(repo_context)["normalized"]


def _normalize_repo_context(repo_context: dict) -> tuple[dict, list[str]]:
    normalized = {}
    warnings = []

    for field in STRING_FIELDS:
        value = _clean_string(repo_context.get(field))
        if value:
            normalized[field] = value

    for field in LIST_FIELDS:
        values = _clean_list(repo_context.get(field))
        if values:
            normalized[field] = values

    extra_fields = sorted(
        key for key in repo_context if key not in STRING_FIELDS and key not in LIST_FIELDS
    )
    if extra_fields:
        normalized["extra"] = {
            key: _safe_extra_value(repo_context[key]) for key in extra_fields[:12]
        }
        warnings.append(
            "Extra fields were preserved under extra: " + ", ".join(extra_fields[:12]) + "."
        )

    return normalized, warnings


def _repo_context_readiness(
    normalized: dict,
    missing_recommended: list[str],
    warnings: list[str],
) -> dict:
    invalid = any(warning.endswith("must be an object.") for warning in warnings)
    if invalid or not normalized:
        level = "missing"
    else:
        has_repo_map = _has_any(normalized, REPO_MAP_FIELDS)
        has_verification = _has_any(normalized, VERIFICATION_FIELDS)
        has_runtime = _has_any(normalized, RUNTIME_FIELDS)

        if missing_recommended:
            level = "partial"
        elif has_repo_map and has_verification and has_runtime:
            level = "implementation_ready"
        elif has_repo_map:
            level = "brief_ready"
        else:
            level = "partial"

    signals = {
        "foundational": _present_fields(normalized, FOUNDATIONAL_FIELDS),
        "repoMap": _present_fields(normalized, REPO_MAP_FIELDS),
        "verification": _present_fields(normalized, VERIFICATION_FIELDS),
        "runtime": _present_fields(normalized, RUNTIME_FIELDS),
        "changeSafety": _present_fields(normalized, ("active_changes",)),
    }
    missing_signals = {
        "foundational": [
            field for field in FOUNDATIONAL_FIELDS if field not in signals["foundational"]
        ],
        "repoMap": [field for field in REPO_MAP_FIELDS if field not in signals["repoMap"]],
        "verification": [
            field for field in VERIFICATION_FIELDS if field not in signals["verification"]
        ],
        "runtime": [field for field in RUNTIME_FIELDS if field not in signals["runtime"]],
        "changeSafety": ["active_changes"] if not signals["changeSafety"] else [],
    }

    return {
        "level": level,
        "readyForBrief": level in {"brief_ready", "implementation_ready"},
        "readyForImplementationBrief": level == "implementation_ready",
        "signals": signals,
        "missingSignals": missing_signals,
        "suggestedAgentNextSteps": _repo_context_next_steps(missing_signals),
    }


def _repo_context_next_steps(missing_signals: dict[str, list[str]]) -> list[str]:
    steps = []
    if missing_signals["foundational"]:
        steps.append("Add source, repo, features, and constraints so Memexai can tailor the brief.")
    if len(missing_signals["repoMap"]) == len(REPO_MAP_FIELDS):
        steps.append(
            "Inspect the repo with filesystem/GitHub/code-index MCP and add relevant files, modules, entrypoints, symbols, or locations."
        )
    if len(missing_signals["verification"]) == len(VERIFICATION_FIELDS):
        steps.append("Add verified commands or tests so the implementation plan has a check path.")
    if len(missing_signals["runtime"]) == len(RUNTIME_FIELDS):
        steps.append(
            "Add dependencies or deployment/runtime facts so saved-video ideas respect the stack."
        )
    if missing_signals["changeSafety"]:
        steps.append(
            "If the repo has active user changes, summarize them in active_changes before proposing edits."
        )
    if not steps:
        steps.append("Repo context is implementation-ready; call build_agent_brief next.")
    return steps


def _repo_context_next_mcp_call(readiness_level: str) -> dict:
    if readiness_level == "implementation_ready":
        return {
            "name": "build_agent_brief",
            "when": "next",
            "reason": (
                "Repo context includes map, verification, and runtime signals, so it is "
                "ready for an implementation-oriented brief."
            ),
            "argumentsTemplate": {
                "query": "implementation goal or product question",
                "repo_context": "normalized repo_context",
                "category_filters": "optional source-label filters",
                "limit": 8,
            },
        }
    if readiness_level == "brief_ready":
        return {
            "name": "build_context_bundle",
            "when": "for_brief",
            "alternate": "build_agent_brief",
            "reason": (
                "Repo context has enough location signal for a source report, spec, or "
                "context bundle; inspect commands, tests, dependencies, and deployment "
                "before asking for implementation guidance."
            ),
            "argumentsTemplate": {
                "query": "learning goal, spec question, or product question",
                "repo_context": "normalized repo_context",
                "category_filters": "optional source-label filters",
                "limit": 8,
            },
        }
    return {
        "name": "validate_repo_context",
        "when": "after_more_repo_inspection",
        "reason": (
            "Repo context is missing or partial. Use the caller's repo/filesystem/GitHub "
            "MCP tools to follow readiness.suggestedAgentNextSteps, then validate again."
        ),
        "argumentsTemplate": {"repo_context": "updated compact repo_context"},
    }


def _has_any(normalized: dict, fields: tuple[str, ...]) -> bool:
    return any(bool(normalized.get(field)) for field in fields)


def _present_fields(normalized: dict, fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if normalized.get(field)]


def _clean_string(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:MAX_STRING_LENGTH].strip()


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        return []

    cleaned = []
    seen = set()
    for item in values:
        text = _clean_string(item)
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        cleaned.append(text)
    return cleaned[:MAX_LIST_ITEMS]


def _safe_extra_value(value: Any) -> Any:
    if isinstance(value, str):
        return _clean_string(value)
    if isinstance(value, list):
        return _clean_list(value)
    if isinstance(value, dict):
        return {
            _clean_string(key): _safe_extra_value(inner_value)
            for key, inner_value in list(value.items())[:12]
            if _clean_string(key)
        }
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    return str(value)[:MAX_STRING_LENGTH]
