-- 021_profile_onboarding_state.sql
-- Durable first-time setup state for resumable FTUE and agent handoff flows.

ALTER TABLE profiles
    ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS onboarding_skipped_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS onboarding_step TEXT NOT NULL DEFAULT 'intro',
    ADD COLUMN IF NOT EXISTS onboarding_state JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS profiles_onboarding_step_idx
    ON profiles(onboarding_step)
    WHERE onboarding_completed_at IS NULL
      AND onboarding_skipped_at IS NULL;
