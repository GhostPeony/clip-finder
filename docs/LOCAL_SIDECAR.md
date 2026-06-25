# Local Postgres Sidecar Prototype

Status: bounded prototype slice, June 22, 2026

## Boundary

The hosted product remains the default and source of record:

- Hosted Supabase/Postgres/pgvector stores canonical videos, chunks, source labels, source
  concepts, knowledge artifacts, user grants, MCP tokens, jobs, and quotas.
- Hosted MCP exports only the current user's granted context. It does not expose the global video
  corpus.
- Hosted ingestion and search still enforce the app's quota, access, and BYOK settings.

The local sidecar is user-owned and read-only from the agent's point of view:

- A user runs local Postgres with pgvector.
- The sidecar mirrors compact `export_brain_digest` rows into a local schema.
- Agents can query the mirror for saved-video context without direct access to hosted Supabase.
- The mirror is not canonical. If hosted grants are revoked, the local sync process should stop
  importing that source and the user should remove old local rows according to their retention
  policy.

This slice deliberately avoids a broad database picker. It proves a small sync contract first:
compact videos, source labels, source concepts, knowledge artifacts, agent notes, personal concepts,
access provenance, and sync cursor metadata.

## Model Spend And BYOK

There are two user-owned spend paths:

- Hosted BYOK: the user stores a provider API key in Memexai settings. The backend encrypts
  the key and can use it for hosted AI requests when `SEARCHTUBE_API_KEY_MODE` allows BYOK or hybrid
  mode. Hosted storage, queue, and transcript quotas still apply.
- Local runner: the user's own Codex, ChatGPT, Claude, Ollama, or other local/desktop agent spends
  through its own authentication or local model setup while reading sidecar data.

Do not describe hosted Memexai as spending a user's ChatGPT/Codex subscription. Codex
subscription auth belongs inside the user's Codex app, CLI, IDE, or cloud environment. Hosted
Memexai can expose MCP context to that agent, or use user-provided API keys for supported
backend model calls, but it cannot currently bill hosted server work to a user's Codex subscription.

## Script

Use [scripts/local_sidecar_digest.py](../scripts/local_sidecar_digest.py) to produce JSONL and SQL.
The script uses only the Python standard library.

Print the local schema:

```bash
python scripts/local_sidecar_digest.py schema --output sidecar_schema.sql
```

Pull compact digest rows from MCP into JSONL:

```bash
python scripts/local_sidecar_digest.py pull \
  --endpoint https://api.memexai.xyz/mcp \
  --token "$MEMEXAI_MCP_TOKEN" \
  --limit 20 \
  --detail-level compact \
  --output brain.jsonl
```

If you need the next cursor, keep a raw digest JSON copy:

```bash
python scripts/local_sidecar_digest.py pull \
  --endpoint https://api.memexai.xyz/mcp \
  --token "$MEMEXAI_MCP_TOKEN" \
  --raw-json \
  --output brain.digest.json
```

Convert raw digest JSON into normalized JSONL:

```bash
python scripts/local_sidecar_digest.py jsonl brain.digest.json --output brain.jsonl
```

Generate idempotent schema plus upsert SQL:

```bash
python scripts/local_sidecar_digest.py sql brain.jsonl \
  --schema-sql \
  --digest brain.digest.json \
  --output sidecar_import.sql
```

Apply it to a user-owned local database:

```bash
psql "$LOCAL_SIDECAR_DATABASE_URL" -f sidecar_import.sql
```

The generated SQL creates:

- `memexai_sidecar.mirror_records`: compact JSONB mirror rows with text-search columns.
- `memexai_sidecar.videos`: video/read provenance view.
- `memexai_sidecar.source_context`: labels, concepts, and artifacts.
- `memexai_sidecar.personal_overlay`: notes and personal concepts.
- `memexai_sidecar.sync_state`: cursor and last digest metadata.

`mirror_records.embedding vector(768)` is nullable. This prototype does not generate embeddings; it
keeps a pgvector-compatible place for later local embedding or rerank experiments without spending
model quota during sync.

## Agent Use

Recommended local agent flow:

1. Use hosted MCP to pull `export_brain_digest` with `detail_level=compact`.
2. Import JSONL into local Postgres using the generated upsert SQL.
3. Configure the local agent with a read-only Postgres user that can `SELECT` from the sidecar
   schema.
4. Search `source_context` and `personal_overlay` locally for planning context.
5. Pull exact timestamp evidence from hosted MCP when the agent needs fresh transcript clips,
   permission checks, or citations beyond the compact mirror.

Local agent writes should go to the personal overlay through hosted MCP tools such as
`add_context_note` or `upsert_personal_concept`, not by mutating mirrored source rows directly.
