-- 030_mcp_token_oauth_client.sql
-- Link OAuth-minted MCP tokens back to their registered OAuth client.

ALTER TABLE mcp_tokens
    ADD COLUMN IF NOT EXISTS oauth_client_id TEXT
        REFERENCES mcp_oauth_clients(client_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS mcp_tokens_oauth_client_idx
    ON mcp_tokens(oauth_client_id);
