-- 020_mcp_oauth_authorization.sql
-- OAuth-native MCP onboarding for agent clients.

CREATE TABLE IF NOT EXISTS mcp_oauth_clients (
    client_id TEXT PRIMARY KEY,
    client_name TEXT NOT NULL DEFAULT 'MCP client',
    redirect_uris TEXT[] NOT NULL DEFAULT '{}',
    client_uri TEXT,
    logo_uri TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS mcp_oauth_authorization_codes (
    code_hash TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL REFERENCES mcp_oauth_clients(client_id) ON DELETE CASCADE,
    redirect_uri TEXT NOT NULL,
    code_challenge TEXT NOT NULL,
    code_challenge_method TEXT NOT NULL DEFAULT 'S256'
        CHECK (code_challenge_method IN ('S256')),
    scopes TEXT[] NOT NULL DEFAULT ARRAY['context:read', 'overlay:write'],
    resource TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS mcp_oauth_authorization_codes_user_created_idx
    ON mcp_oauth_authorization_codes(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS mcp_oauth_authorization_codes_client_created_idx
    ON mcp_oauth_authorization_codes(client_id, created_at DESC);

ALTER TABLE mcp_oauth_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_oauth_authorization_codes ENABLE ROW LEVEL SECURITY;

-- Managed exclusively by backend service-role endpoints. No browser RLS policy
-- exposes client metadata or short-lived authorization codes directly.
