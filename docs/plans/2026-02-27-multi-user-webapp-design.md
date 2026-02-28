# ClipSeek Multi-User Web App Design

**Date:** 2026-02-27
**Status:** Approved
**Approach:** Supabase Full Stack (Auth + PostgreSQL/pgvector + managed infrastructure)

## Problem

ClipSeek is currently a single-user, self-hosted RAG app for YouTube transcript search. We want to make it a multi-user web app where anyone can sign in, index YouTube videos, and search across their library -- without over-engineering or locking into expensive infrastructure.

## Decisions Made

- **PageIndex rejected** -- solves a different problem (deep single-document retrieval for structured PDFs). ClipSeek needs cross-document search over thousands of short transcript chunks with rich metadata. Vector DB is the correct tool.
- **Supabase chosen** over serverless multi-vendor (too many services) and self-hosted Docker (too much ops burden). Supabase gives auth + relational DB + pgvector in one platform with a generous free tier.
- **OAuth only** (Google/GitHub) -- no passwords to manage.
- **BYOK + free tier** -- users get a free quota, can add their own Gemini API key for unlimited use.
- **Shared-on-demand data model** -- indexed content is global. If User A indexes a channel, User B can subscribe instantly without re-indexing.
- **Metering by video count**, not channel count -- channels vary wildly in size.

## Architecture

```
Frontend (React + Vite + Tailwind + Supabase SDK)
    │ JWT auth
    ▼
FastAPI Backend (Railway / Fly.io)
    │ validates JWT, enforces quotas
    ▼
Supabase Platform
    ├── Auth (Google/GitHub OAuth)
    ├── PostgreSQL + pgvector (all data)
    └── Row-Level Security (data scoping)
```

### What stays the same
- React frontend structure (UnifiedSearchView, VideoPlayer, AnswerSection, Library)
- FastAPI as compute backend for ingestion and search
- SSE streaming for ingestion progress
- YouTube scraping pipeline (scrapetube + youtube-transcript-api)
- Same chunking strategy (60-second segments)

### What changes
- ChromaDB replaced by pgvector in Supabase PostgreSQL
- Supabase Auth replaces no-auth
- JWT middleware added to all FastAPI endpoints
- API key storage moves from localStorage to encrypted server-side (Supabase Vault)
- Search history moves from localStorage to database
- Library view scoped to user's subscribed channels
- Usage metering added

## Database Schema

### profiles
| Column | Type | Notes |
|---|---|---|
| id | uuid (FK auth.users) | Primary key, matches Supabase auth user |
| display_name | text | From OAuth provider |
| avatar_url | text | From OAuth provider |
| api_key_enc | text (nullable) | Gemini API key, encrypted via Supabase Vault |
| free_searches_today | int | Resets daily, default 0 |
| free_indexes_this_month | int | Resets monthly, default 0 |
| created_at | timestamptz | |

### channels
| Column | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| youtube_handle | text (unique) | e.g., `@3Blue1Brown` |
| name | text | Display name |
| total_videos | int | Count of indexed videos |
| indexed_at | timestamptz | Last full index time |
| indexed_by | uuid (FK profiles) | User who first indexed |

### user_channels (join table)
| Column | Type | Notes |
|---|---|---|
| user_id | uuid (FK profiles) | |
| channel_id | uuid (FK channels) | |
| added_at | timestamptz | When user subscribed |
| PRIMARY KEY | (user_id, channel_id) | |

### videos
| Column | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| channel_id | uuid (FK channels) | |
| youtube_video_id | text (unique) | YouTube video ID |
| title | text | |
| thumbnail_url | text | |
| indexed_at | timestamptz | |

### chunks
| Column | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| video_id | uuid (FK videos) | |
| content | text | Transcript text |
| start_seconds | int | Chunk start time |
| end_seconds | int | Chunk end time |
| embedding | vector(768) | pgvector column |

### usage_logs
| Column | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| user_id | uuid (FK profiles) | |
| action | text | `search` or `index` |
| video_count | int (nullable) | For index actions |
| used_own_key | bool | Whether BYOK was active |
| created_at | timestamptz | |

### search_history
| Column | Type | Notes |
|---|---|---|
| id | uuid | Primary key |
| user_id | uuid (FK profiles) | |
| query | text | |
| result_clip_ids | uuid[] | References to chunks |
| created_at | timestamptz | |

## Shared-on-Demand Data Flow

1. **User A** indexes `@3Blue1Brown`:
   - `channels` row created with youtube_handle
   - Videos scraped, `videos` rows created
   - Transcripts chunked, embedded, `chunks` rows created
   - `user_channels` row links User A to the channel
   - User A's `free_indexes_this_month` incremented by video count

2. **User B** tries to index `@3Blue1Brown`:
   - Backend detects channel already exists (youtube_handle match)
   - No scraping, no embedding -- just creates `user_channels` row
   - User B's quota is NOT charged (no API calls made)
   - If channel has new videos since last index, only new videos are processed

3. **User B searches**:
   - Query embedding generated
   - pgvector similarity search scoped to channels in User B's `user_channels`
   - Results returned with video metadata for timestamp links

## Free Tier Metering

| Resource | Free limit | BYOK limit |
|---|---|---|
| Searches | 20/day | Unlimited |
| Video indexing | 50 videos/month | Unlimited |

- Subscribing to already-indexed content costs zero quota
- Usage tracked in `usage_logs` table
- `used_own_key` boolean determines whether it counts against free tier
- Daily search counter resets at midnight UTC
- Monthly index counter resets on 1st of month

## API Cost Analysis

Using `gemini-embedding-001` + `gemini-2.5-flash-lite`:

| Scenario | Monthly cost |
|---|---|
| 100 users, 20 searches/day each | ~$16/month |
| 100 users, 20 searches/day, gemini-2.5-flash | ~$68/month |
| 1,000 users | ~$160-680/month |

Rate limits (not cost) are the constraint. Tier 1 (enable billing) required for multi-user. Tier 2 ($250 cumulative spend) needed for 100+ active users.

## Model Migration Required

- `text-embedding-004` deprecated Jan 2026 -- migrate to `gemini-embedding-001`
- `gemini-2.0-flash` retiring March 2026 -- migrate to `gemini-2.5-flash-lite` (same price) or `gemini-2.5-flash`

## API Endpoint Changes

| Endpoint | Auth | Changes |
|---|---|---|
| `POST /api/ingest` | Required | Checks quota, writes to pgvector, creates user_channels link |
| `POST /api/search` | Required | Checks quota, scopes search to user's channels |
| `GET /api/library` | Required | Returns only user's subscribed channels |
| `DELETE /api/video/{id}` | Required | Removes user_channels link; deletes global data only if no subscribers |
| `GET /api/usage` | Required | NEW: returns quota status |
| `PUT /api/settings/key` | Required | NEW: saves encrypted API key |
| `POST /api/channel/rename` | Required | Scoped to user's channels |
| `GET /api/transcript/{id}` | Required | Scoped to user's channels |

### Search Query (pgvector)

```sql
SELECT c.content, c.start_seconds, c.end_seconds,
       v.youtube_video_id, v.title, v.thumbnail_url
FROM chunks c
JOIN videos v ON c.video_id = v.id
JOIN channels ch ON v.channel_id = ch.id
JOIN user_channels uc ON ch.id = uc.channel_id
WHERE uc.user_id = :current_user_id
ORDER BY c.embedding <=> :query_embedding
LIMIT 5;
```

## Frontend Changes

- Add Supabase SDK for auth (login/logout, JWT management)
- Route guards: search/ingest/library require auth, landing page is public
- API client attaches `Authorization: Bearer <jwt>` to all requests
- API key management moves from localStorage to server-side encrypted storage
- Library view scoped to user's subscribed channels
- Search history persists in database (cross-device)
- Add usage dashboard showing remaining free quota

## Deployment

| Service | Platform | Cost |
|---|---|---|
| Frontend | Vercel or Netlify | Free tier |
| Backend (FastAPI) | Railway or Fly.io | Free tier / ~$5/month |
| Database + Auth | Supabase | Free tier (500MB) / $25/month Pro |
| Gemini API | Google AI | ~$16-68/month at 100 users |

## Out of Scope (for now)

- Paid subscription tiers / Stripe billing
- Admin dashboard
- Content moderation
- Email notifications
- Mobile app
- Real-time collaboration
- Video upload (non-YouTube sources)
