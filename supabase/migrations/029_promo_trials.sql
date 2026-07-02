-- 029_promo_trials.sql
-- Track one-time promotional trial redemptions per billing profile.

ALTER TABLE billing_profiles
    ADD COLUMN IF NOT EXISTS promo_trial_code TEXT,
    ADD COLUMN IF NOT EXISTS promo_trial_redeemed_at TIMESTAMPTZ;
