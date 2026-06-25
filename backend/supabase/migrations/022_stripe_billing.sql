-- 022_stripe_billing.sql
-- Hosted Stripe subscription state and billing-period usage counters.

CREATE TABLE IF NOT EXISTS billing_profiles (
    user_id UUID PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT UNIQUE,
    stripe_price_id TEXT,
    price_lookup_key TEXT,
    plan_key TEXT NOT NULL DEFAULT 'free'
        CHECK (plan_key IN ('free', 'plus', 'pro')),
    billing_status TEXT NOT NULL DEFAULT 'free'
        CHECK (billing_status IN (
            'free',
            'trialing',
            'active',
            'past_due',
            'canceled',
            'incomplete',
            'incomplete_expired',
            'unpaid'
        )),
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
    usage_pack_seconds_balance INT NOT NULL DEFAULT 0 CHECK (usage_pack_seconds_balance >= 0),
    last_stripe_event_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS billing_profiles_customer_idx
    ON billing_profiles(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS billing_profiles_subscription_idx
    ON billing_profiles(stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS billing_profiles_plan_status_idx
    ON billing_profiles(plan_key, billing_status);

CREATE TABLE IF NOT EXISTS billing_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    processed_at TIMESTAMPTZ,
    processing_status TEXT NOT NULL DEFAULT 'processing'
        CHECK (processing_status IN ('processing', 'processed', 'ignored', 'failed')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS billing_events_type_created_idx
    ON billing_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS billing_events_customer_idx
    ON billing_events(stripe_customer_id)
    WHERE stripe_customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS billing_events_subscription_idx
    ON billing_events(stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS billing_period_usage (
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    retrieval_calls INT NOT NULL DEFAULT 0 CHECK (retrieval_calls >= 0),
    indexed_transcript_seconds INT NOT NULL DEFAULT 0 CHECK (indexed_transcript_seconds >= 0),
    deep_indexed_transcript_seconds INT NOT NULL DEFAULT 0
        CHECK (deep_indexed_transcript_seconds >= 0),
    ingestion_jobs_started INT NOT NULL DEFAULT 0 CHECK (ingestion_jobs_started >= 0),
    indexed_videos_added INT NOT NULL DEFAULT 0 CHECK (indexed_videos_added >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, period_start, period_end),
    CHECK (period_end > period_start)
);

CREATE INDEX IF NOT EXISTS billing_period_usage_user_period_idx
    ON billing_period_usage(user_id, period_start DESC, period_end DESC);

DROP TRIGGER IF EXISTS billing_profiles_touch_updated_at ON billing_profiles;
CREATE TRIGGER billing_profiles_touch_updated_at
    BEFORE UPDATE ON billing_profiles
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

DROP TRIGGER IF EXISTS billing_period_usage_touch_updated_at ON billing_period_usage;
CREATE TRIGGER billing_period_usage_touch_updated_at
    BEFORE UPDATE ON billing_period_usage
    FOR EACH ROW EXECUTE FUNCTION touch_context_updated_at();

ALTER TABLE billing_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_period_usage ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS billing_profiles_select ON billing_profiles;
DROP POLICY IF EXISTS billing_period_usage_select ON billing_period_usage;

CREATE POLICY billing_profiles_select ON billing_profiles
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY billing_period_usage_select ON billing_period_usage
    FOR SELECT USING (auth.uid() = user_id);

-- billing_events intentionally has no client policies. It is written and read
-- only by the backend service role for webhook idempotency and diagnostics.
