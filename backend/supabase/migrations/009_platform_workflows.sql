-- 009_platform_workflows.sql
-- Versioned platform workflow definitions and durable workflow instance status.

CREATE TABLE IF NOT EXISTS workflow_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    version INT NOT NULL DEFAULT 1 CHECK (version > 0),
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    trigger TEXT NOT NULL DEFAULT '',
    steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    policies JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('draft', 'active', 'archived')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'system'
        CHECK (created_by IN ('system', 'user', 'agent')),
    created_by_client TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, key, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS workflow_definitions_global_key_version_idx
    ON workflow_definitions(key, version)
    WHERE user_id IS NULL;
CREATE INDEX IF NOT EXISTS workflow_definitions_user_key_idx
    ON workflow_definitions(user_id, key, version DESC);

CREATE TABLE IF NOT EXISTS workflow_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    workflow_definition_id UUID REFERENCES workflow_definitions(id) ON DELETE SET NULL,
    workflow_key TEXT NOT NULL,
    workflow_version INT NOT NULL DEFAULT 1 CHECK (workflow_version > 0),
    trigger TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'waiting', 'completed', 'failed', 'cancelled')),
    input JSONB NOT NULL DEFAULT '{}'::jsonb,
    current_step TEXT,
    cost_estimate JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by TEXT NOT NULL DEFAULT 'system'
        CHECK (created_by IN ('system', 'user', 'agent')),
    created_by_client TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS workflow_instances_user_created_idx
    ON workflow_instances(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS workflow_instances_user_status_idx
    ON workflow_instances(user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS workflow_instances_key_version_idx
    ON workflow_instances(workflow_key, workflow_version);

CREATE TABLE IF NOT EXISTS workflow_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_instance_id UUID NOT NULL REFERENCES workflow_instances(id) ON DELETE CASCADE,
    step_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'waiting', 'completed', 'failed', 'skipped', 'cancelled')),
    attempt INT NOT NULL DEFAULT 1 CHECK (attempt > 0),
    input_ref JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_ref JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS workflow_steps_instance_created_idx
    ON workflow_steps(workflow_instance_id, created_at);
CREATE INDEX IF NOT EXISTS workflow_steps_instance_step_idx
    ON workflow_steps(workflow_instance_id, step_key, attempt DESC);

CREATE TABLE IF NOT EXISTS workflow_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_instance_id UUID NOT NULL REFERENCES workflow_instances(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'archived')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS workflow_artifacts_instance_type_idx
    ON workflow_artifacts(workflow_instance_id, artifact_type);

DROP TRIGGER IF EXISTS workflow_definitions_touch_updated_at ON workflow_definitions;
CREATE TRIGGER workflow_definitions_touch_updated_at
    BEFORE UPDATE ON workflow_definitions
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

DROP TRIGGER IF EXISTS workflow_instances_touch_updated_at ON workflow_instances;
CREATE TRIGGER workflow_instances_touch_updated_at
    BEFORE UPDATE ON workflow_instances
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

DROP TRIGGER IF EXISTS workflow_artifacts_touch_updated_at ON workflow_artifacts;
CREATE TRIGGER workflow_artifacts_touch_updated_at
    BEFORE UPDATE ON workflow_artifacts
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

ALTER TABLE workflow_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_instances ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_artifacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY workflow_definitions_select ON workflow_definitions
    FOR SELECT USING (user_id IS NULL OR auth.uid() = user_id);

CREATE POLICY workflow_instances_select ON workflow_instances
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY workflow_steps_select ON workflow_steps
    FOR SELECT USING (
        EXISTS (
            SELECT 1
            FROM workflow_instances wi
            WHERE wi.id = workflow_steps.workflow_instance_id
              AND wi.user_id = auth.uid()
        )
    );

CREATE POLICY workflow_artifacts_select ON workflow_artifacts
    FOR SELECT USING (
        EXISTS (
            SELECT 1
            FROM workflow_instances wi
            WHERE wi.id = workflow_artifacts.workflow_instance_id
              AND wi.user_id = auth.uid()
        )
    );
