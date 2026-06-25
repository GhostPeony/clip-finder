-- 006_mcp_tokens.sql
-- User-scoped MCP bearer tokens for remote agent access.

CREATE TABLE IF NOT EXISTS mcp_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT 'MCP token',
    token_hash TEXT NOT NULL UNIQUE,
    token_prefix TEXT NOT NULL,
    scopes TEXT[] NOT NULL DEFAULT ARRAY['context:read', 'overlay:write'],
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS mcp_tokens_user_created_idx
    ON mcp_tokens(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS mcp_tokens_hash_idx ON mcp_tokens(token_hash);

ALTER TABLE mcp_tokens ENABLE ROW LEVEL SECURITY;

-- Deliberately no client RLS policies. Tokens are managed through the backend
-- service role so token_hash is never exposed through the browser client.
