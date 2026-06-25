from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERMES_SKILL = ROOT / "integrations" / "hermes" / "memexai-context" / "SKILL.md"
HERMES_MCP_SNIPPET = ROOT / "integrations" / "hermes" / "mcp_servers.memexai.example.yaml"


def test_hermes_skill_documents_low_friction_repo_context_flow():
    text = HERMES_SKILL.read_text(encoding="utf-8")

    assert "name: memexai-context" in text
    assert "repo_context" in text
    assert "get_mcp_session" in text
    assert '"locations"' in text
    assert '"symbols"' in text
    assert "get_agent_quickstart" in text
    assert "context://agent-quickstart" in text
    assert "get_repo_context_contract" in text
    assert "context://repo-context-contract" in text
    assert "validate_repo_context" in text
    assert "readiness.level" in text
    assert "implementation_ready" in text
    assert "readiness loop" in text
    assert "collect_repo_context" in text
    assert "build_agent_brief" in text
    assert "repoFit.targetMap" in text
    assert "library videos, and video context" in text
    assert "repo, filesystem, GitHub, or code-index tools" in text


def test_hermes_skill_keeps_source_context_read_only():
    text = HERMES_SKILL.read_text(encoding="utf-8")

    assert "Treat source video context as read-only." in text
    assert "Do not rewrite transcripts" in text
    assert "add_context_note" in text
    assert "upsert_personal_concept" in text


def test_hermes_skill_documents_ingestion_guardrails_and_sierra_sample():
    text = HERMES_SKILL.read_text(encoding="utf-8")

    assert "queue_youtube_ingestion" in text
    assert "allow_bulk: true" in text
    assert "explicit user approval" in text
    assert "uCKhOmth2ms" in text


def test_hermes_mcp_snippet_uses_env_token_not_raw_secret():
    text = HERMES_MCP_SNIPPET.read_text(encoding="utf-8")

    assert "memexai:" in text
    assert "https://api.memexai.xyz/mcp" in text
    assert "Bearer ${MEMEXAI_MCP_TOKEN}" in text
    assert "Do not paste raw tokens into this repo" in text
    assert "Bearer mcp_" not in text.lower()
