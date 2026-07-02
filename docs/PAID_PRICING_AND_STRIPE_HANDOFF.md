# Paid Pricing And Stripe Handoff

Status: approved individual paid-usage spec for Stripe implementation planning.

Owner handoff: this document is for the agent implementing Stripe billing, quota resolution, and paid usage enforcement.

Date approved: 2026-06-24.

## Decision

Memexai paid usage should be priced by transcript hours, not by raw video count.

The product value is not "number of videos stored." It is how much video context Memexai can ingest, analyze, retrieve, and expose to humans and MCP agents. A 3-minute clip and a 2-hour lecture should not consume the same amount of paid allowance.

Approved v1 scope:

- Free
- Plus
- Pro
- Optional transcript-hour packs after subscription billing is working

Explicitly out of scope:

- Team pricing
- seat billing
- shared team workspaces
- SSO/SCIM/admin billing

Reason: there is not enough signal yet that Memexai is a team/workspace product. Keep pricing individual until usage proves teams need shared libraries, admin controls, or pooled billing.

## Market Research Snapshot

Comparable products cluster into two pricing patterns.

Knowledge-base and read-later products charge around $10 to $15/month for personal use:

- Recall: Free, Plus at $10/month billed yearly, Max at $38/month billed yearly. Recall includes AI summaries, knowledge graph, chat, API, and MCP access.
- Readwise with Reader: $9.99/month billed annually or $12.99 monthly.
- Mem: Free with usage caps, Pro around $12/month or $14.99 headline pricing depending on page treatment, with unlimited notes/chat/search.
- mymind: Mastermind at $12.99 monthly or $129 yearly.

Transcription-heavy products charge around $10 to $30/month with minute/storage/import/AI limits:

- Fireflies: Free, Pro at $10/seat/month annually or $18 monthly, Business at $19/seat/month annually or $29 monthly. Limits include storage minutes and AI credits.
- Otter: Basic free with 300 monthly transcription minutes, Pro around $8.33 annually or $16.99 monthly with 1,200 monthly minutes and file import limits, Business around $19.99 annually.

Conclusion: Plus should feel like a personal knowledge subscription near $10 to $12/month. Pro should sit near $25 to $30/month for heavy researchers and agent users. Avoid "unlimited" as the core promise. Use clear transcript-hour quotas and hard caps.

Sources:

- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Fireflies pricing: https://fireflies.ai/pricing
- Otter pricing: https://otter.ai/pricing
- Recall pricing: https://www.recall.it/pricing
- Readwise pricing: https://readwise.io/pricing/reader
- Mem pricing: https://get.mem.ai/pricing
- mymind pricing: https://mymind.com/pricing

## Internal Cost Model

Current Memexai ingestion uses:

- Embeddings: `gemini-embedding-001`
- LLM digestion: `gemini-3.1-flash-lite`
- Default video analysis depth: `standard`

Current model-only estimate for a new 15-minute video:

| Depth      | Approx standard model cost |
| ---------- | -------------------------: |
| `none`     |                   $0.00054 |
| `basic`    |       $0.00294 upper bound |
| `standard` |       $0.01118 upper bound |
| `deep`     |       $0.02115 upper bound |

Approx model-only cost per transcript hour:

| Depth      | Approx model cost per hour |
| ---------- | -------------------------: |
| `standard` |       $0.04472 upper bound |
| `deep`     |       $0.08460 upper bound |

These are not the full cost of service. Stripe pricing must also leave room for:

- Supabase database rows, vector indexes, storage, and egress
- Cloudflare/container/queue runtime
- YouTube API quota and transcript-fetch retries
- support and operational overhead
- abuse, retries, duplicate jobs, and long-tail storage
- future richer reports or reprocessing

Pricing should therefore be value-priced with transcript-hour guardrails, not a markup over Gemini tokens.

## Approved Tiers

### Free

Purpose: let a user prove the value of saved-video memory and MCP retrieval before paying.

Price:

- $0
- no card required
- no Stripe trial needed

Entitlements:

- 5 lifetime indexed transcript hours
- 15 indexed videos total as a secondary abuse cap
- 100 search/MCP retrieval calls per month
- 10 videos per import batch
- 5 max search results per query
- 1 active ingestion job
- standard analysis on every indexed video
- OAuth MCP access can remain available, but all read/write actions must respect free quotas

Maps to current defaults:

- `DEFAULT_FREE_SEARCHES_PER_MONTH = 100`
- `DEFAULT_FREE_INDEXED_VIDEOS_TOTAL = 15`
- `DEFAULT_FREE_INDEXED_TRANSCRIPT_SECONDS_TOTAL = 18_000`
- `DEFAULT_FREE_MAX_IMPORT_VIDEOS = 10`
- `DEFAULT_FREE_MAX_SEARCH_RESULTS = 5`
- `DEFAULT_FREE_MAX_ACTIVE_INGESTION_JOBS = 1`

### Plus

Purpose: the default paid plan for an individual building a durable video knowledge base.

Price:

- $12/month
- $120/year, equivalent to $10/month annually

Stripe lookup keys:

- `memexai_plus_monthly_v1`
- `memexai_plus_annual_v1`

Entitlements:

- 50 new indexed transcript hours per billing month
- 500 total library transcript hours
- 1,000 indexed videos total as a secondary abuse cap
- 2,000 search/MCP retrieval calls per month
- 25 videos per import batch
- 10 max search results per query
- 2 active ingestion jobs
- standard analysis on every indexed video
- MCP OAuth access
- capture-source sync
- saved video library and timestamp topic retrieval

Deep analysis:

- Not included as a separate visible feature in Plus v1.
- If an internal or agent path allows `deep`, it should consume 2x transcript-hour allowance or require Pro.

### Pro

Purpose: heavy individual usage for researchers, builders, and agent-heavy workflows.

Price:

- $29/month
- $288/year, equivalent to $24/month annually

Stripe lookup keys:

- `memexai_pro_monthly_v1`
- `memexai_pro_annual_v1`

Entitlements:

- 200 new indexed transcript hours per billing month
- 2,000 total library transcript hours
- 5,000 indexed videos total as a secondary abuse cap
- 10,000 search/MCP retrieval calls per month
- 100 videos per import batch
- 20 max search results per query
- 5 active ingestion jobs
- priority ingestion queue
- standard analysis on every indexed video
- 50 deep-analysis transcript hours per month
- deep analysis beyond included allowance consumes 2x transcript-hour allowance or requires a usage pack

## Usage Packs

Do not block subscription launch on packs. Implement Plus and Pro first.

Recommended add-on after base billing is stable:

- Product: `memexai_transcript_hour_pack`
- Price: $10 one-time
- Entitlement: 100 additional standard transcript hours
- Stripe lookup key: `memexai_transcript_hours_100_v1`
- Deep analysis consumes pack balance at 2x
- Pack balance is app-side state, not a new subscription

Recommended behavior:

- Packs are consumed only after monthly plan allowance is exhausted.
- Packs do not raise total library-hour caps by default unless explicitly decided later.
- Packs should expire after 12 months or at account cancellation to avoid unbounded accounting liability.
- No automatic overage billing in v1. The product should hit a clear limit and offer upgrade or pack purchase.

## Trial And Upgrade Policy

No self-serve Stripe trial in v1. Free is the trial for organic signups.

Amendment (2026-07-01): promotional launch links may grant a Stripe-managed plan trial.

- Signup links carry `?promo=CODE` (e.g. Product Hunt). Codes are configured via `PROMO_TRIAL_CODES=code:plan:days`.
- Redemption happens through the app's authenticated Checkout endpoint with `subscription_data.trial_period_days`, `payment_method_collection=if_required` (no card), and `trial_settings.end_behavior.missing_payment_method=cancel` (no surprise charges).
- One redemption per account (`billing_profiles.promo_trial_code/promo_trial_redeemed_at`, migration 029), new subscribers only.
- Trialing subscriptions receive full paid entitlements because `trialing` is an active billing status; trial expiry arrives through the normal subscription webhooks.

Recommended paid behavior:

- Upgrade takes effect immediately after Checkout success.
- Downgrade/cancellation takes effect at period end.
- Past-due users keep read access to already indexed content for a grace period, but new ingestion and high-volume MCP retrieval should be blocked or reduced to Free limits.
- Existing indexed content should not be deleted on downgrade. New ingestion and retrieval limits should change.

## BYOK Policy

BYOK should not bypass hosted plan quotas in v1.

Reason: even if the user supplies an AI key later, Memexai still pays for database storage, workers, queueing, orchestration, retries, support, and hosted retrieval traffic. BYOK can become a future way to reduce model-cost exposure, but it should not make hosted ingestion unlimited.

Recommended rule:

- Hosted quota enforcement is based on plan entitlements.
- BYOK, if exposed later, affects model provider billing only.
- Do not mention BYOK in customer pricing copy for v1.

## Stripe Catalog

Create products/prices in Stripe sandbox first, then mirror lookup keys in production.

Products:

- `Memexai Plus`
- `Memexai Pro`
- `Memexai Transcript Hours`

Prices:

| Product                  | Lookup key                        |    Amount | Mode              |
| ------------------------ | --------------------------------- | --------: | ----------------- |
| Memexai Plus             | `memexai_plus_monthly_v1`         | $12/month | recurring monthly |
| Memexai Plus             | `memexai_plus_annual_v1`          | $120/year | recurring annual  |
| Memexai Pro              | `memexai_pro_monthly_v1`          | $29/month | recurring monthly |
| Memexai Pro              | `memexai_pro_annual_v1`           | $288/year | recurring annual  |
| Memexai Transcript Hours | `memexai_transcript_hours_100_v1` |       $10 | one-time          |

Do not create a Team product for v1.

## Billing State

Add or map persistent billing state per Supabase user.

Recommended table: `billing_profiles`

Fields:

- `user_id`
- `stripe_customer_id`
- `stripe_subscription_id`
- `stripe_price_id`
- `price_lookup_key`
- `plan_key`: `free`, `plus`, `pro`
- `billing_status`: `free`, `trialing`, `active`, `past_due`, `canceled`, `incomplete`, `incomplete_expired`, `unpaid`
- `current_period_start`
- `current_period_end`
- `cancel_at_period_end`
- `usage_pack_seconds_balance`
- `last_stripe_event_id`
- `created_at`
- `updated_at`

Recommended table: `billing_events`

Fields:

- `stripe_event_id`
- `event_type`
- `stripe_customer_id`
- `stripe_subscription_id`
- `processed_at`
- `processing_status`
- `error_message`

`stripe_event_id` must be unique so webhook processing is idempotent.

## Entitlement Resolution

Create one backend function that resolves effective limits:

`resolve_user_entitlements(user_id) -> PlanEntitlements`

Suggested shape:

```json
{
  "planKey": "plus",
  "billingStatus": "active",
  "monthlyIndexedTranscriptSeconds": 180000,
  "libraryTranscriptSeconds": 1800000,
  "indexedVideosTotal": 1000,
  "monthlyRetrievalCalls": 2000,
  "maxImportVideos": 25,
  "maxSearchResults": 10,
  "maxActiveIngestionJobs": 2,
  "deepTranscriptSeconds": 0,
  "priorityQueue": false,
  "usagePackSecondsBalance": 0
}
```

Use this function everywhere quotas are checked:

- search and MCP retrieval
- single video ingestion
- playlist/capture-source sync
- batch import size
- active ingestion jobs
- result limits
- deep-analysis requests

Avoid duplicating plan constants across route handlers.

## Monthly Usage Counters

Track usage by billing period, not only by calendar month.

Recommended usage keys:

- `indexed_transcript_seconds`
- `deep_indexed_transcript_seconds`
- `retrieval_calls`
- `ingestion_jobs_started`
- `indexed_videos_added`

Important accounting rules:

- Already indexed videos granted to a user should count against library totals, but should not consume monthly new-indexing transcript hours if no new digestion/embedding was generated.
- Failed jobs should not consume transcript-hour quota unless they created durable artifacts.
- Retried jobs should not double-count successful transcript seconds.
- Playlist/capture-source sync should check projected transcript seconds when known, and fall back to conservative per-video batch caps when transcript length is unknown.

## API Endpoints

Backend endpoints for the Stripe agent to implement:

- `POST /api/billing/checkout`
- `POST /api/billing/portal`
- `GET /api/billing/status`
- `POST /api/billing/webhook`

`POST /api/billing/checkout`

- Auth required.
- Input: `{ "lookupKey": "memexai_plus_monthly_v1" }`
- Creates or reuses a Stripe customer for the current Supabase user.
- Creates a Checkout subscription session for Plus/Pro recurring prices.
- Creates a Checkout payment session for transcript-hour packs if packs are implemented.
- Returns `{ "url": "https://checkout.stripe.com/..." }`.

`POST /api/billing/portal`

- Auth required.
- Requires existing `stripe_customer_id`.
- Returns a Stripe Customer Portal URL.

`GET /api/billing/status`

- Auth required.
- Returns current plan, billing status, period end, cancel-at-period-end, entitlements, and current usage.
- Frontend and MCP should rely on this instead of hardcoded tier copy.

`POST /api/billing/webhook`

- No app auth.
- Must verify `Stripe-Signature` using the raw request body and `STRIPE_WEBHOOK_SECRET`.
- Must insert `billing_events` before applying state transitions.
- Must ignore already processed event IDs.

## Webhook Events

Minimum webhook events:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

If Stripe Entitlements are used:

- `entitlements.active_entitlement_summary.updated`

For one-time usage packs:

- `payment_intent.succeeded`
- or `checkout.session.completed` for mode `payment`

The backend should derive the active plan from Stripe subscription status plus price lookup key. Do not trust frontend-selected plan names.

## MCP And Agent Behavior

MCP agents should be able to inspect usage and understand limits without using the web dashboard.

Recommended MCP additions after billing state exists:

- `get_usage_status`
- include plan/entitlement fields in `get_mcp_session`
- return structured quota errors from ingestion/search tools

Quota error shape:

```json
{
  "error": "quota_exceeded",
  "quota": "monthly_indexed_transcript_seconds",
  "planKey": "free",
  "used": 18000,
  "limit": 18000,
  "upgradeAvailable": true,
  "billingUrlHint": "/api/billing/checkout"
}
```

Agents can ask the user to approve opening Checkout, but payment should still complete through Stripe-hosted Checkout with the human account in control.

## Frontend Behavior

Keep billing UI operational and compact.

Needed surfaces:

- usage card with current plan and limits
- upgrade action for Free users
- manage billing action for paid users
- limit-reached modal or inline notice
- clear distinction between monthly new transcript hours and total library hours
- no Team language
- no local/BYOK pricing language

Recommended customer copy:

- "Transcript hours" instead of "credits"
- "New indexed this month" instead of "usage burned"
- "Total library" for stored/searchable corpus size
- "Deep analysis uses 2x transcript hours" if exposed

## Implementation Milestones

1. Create Stripe sandbox products and lookup keys for Plus and Pro.
2. Add billing state tables and idempotent event table.
3. Add backend Stripe config and webhook signature verification.
4. Add Checkout, Portal, Status, and Webhook routes.
5. Add `resolve_user_entitlements` and replace free-only quota checks.
6. Add monthly usage counters aligned to the subscription billing period.
7. Add dashboard usage/upgrade/manage billing UI.
8. Add MCP usage visibility and structured quota errors.
9. Verify with Stripe CLI sandbox events.
10. Add optional transcript-hour packs after subscriptions are stable.

## Verification Checklist

Stripe sandbox:

- Free user can create Plus monthly Checkout session.
- Checkout success upgrades user to Plus.
- Customer Portal cancellation sets `cancel_at_period_end`.
- Subscription deletion returns user to Free entitlements at period end.
- Payment failure marks user `past_due`.
- Duplicate webhook event is ignored safely.
- Invalid webhook signature is rejected.
- Annual prices map to the same Plus/Pro plan keys as monthly prices.
- Pro user receives Pro limits.
- Team product does not exist in v1 catalog.

Quota behavior:

- Free user is blocked at 5 transcript hours.
- Plus user is blocked at 50 new transcript hours in the period.
- Pro user is blocked at 200 new transcript hours in the period.
- Already indexed video grant does not consume new indexing quota.
- Deep analysis consumes deep allowance or 2x transcript hours.
- MCP search and ingestion return structured quota errors.

## Open Questions For The Stripe Agent

- Should billing usage periods be anchored to Stripe `current_period_start/end` in DB, or computed from subscription status on every request?
- Should usage packs launch in the first billing PR, or wait until subscription webhooks are stable?
- Should `past_due` users get a short grace period for retrieval, and if yes, how many days?
- Should annual subscribers get a larger monthly reset only, or should unused transcript hours roll over? Recommendation: no rollover in v1.
