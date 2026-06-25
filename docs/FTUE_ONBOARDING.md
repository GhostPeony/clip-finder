# Memexai FTUE Onboarding Scope

Status: scoped, with backend onboarding state foundation implemented.

## Goal

The first-time user experience should turn a signed-in visitor into an activated Memexai user in one short run:

1. They understand that Memexai turns saved YouTube videos into searchable context for humans and agents.
2. They connect YouTube with read-only access.
3. They pick a YouTube playlist to use as their capture inbox.
4. They import the first small batch or one sample video.
5. They leave with an MCP token or setup bundle their agent can use.

The activation event is not "account created." It is:

> User has at least one granted video source and has either run a search or copied an agent setup bundle.

## Product Stance

Use a guided setup, not a generic tutorial.

The onboarding should be short, skippable, and stateful. A user should always know:

- what permission is being requested,
- what Memexai will do with it,
- what their agent can access,
- how to return later if they skip a step.

Do not ask for broad YouTube management scopes in the first run. Keep the first ask to `youtube.readonly`. That lets Memexai read selected playlists and playlist items without asking to manage the user's channel or mutate their YouTube account.

## Recommended Flow

### Entry

Primary landing CTA:

> Start with YouTube

This starts Google OAuth with identity plus YouTube read-only scope when the user chooses the main onboarding path. It should reuse the existing `connectYouTube` path so one consent can both sign the user in and store the provider grant.

Secondary CTA:

> Sign in only

This keeps a lower-pressure path for privacy-sensitive users, users who only want to inspect the app, or users whose Google workspace blocks YouTube scopes.

### Step 1: Plain-English Rundown

Screen purpose:

- Set the frame in one sentence.
- Show the three things they will set up.
- Make the agent angle obvious.

Suggested copy:

> Save videos on YouTube. Memexai turns them into searchable clips, study guides, and agent-ready context.

Setup checklist:

- Connect YouTube
- Choose a save playlist
- Connect an agent

CTA:

- Continue
- Skip setup

### Step 2: Connect YouTube

Screen purpose:

- Request `youtube.readonly`.
- Explain the boundary.
- Avoid making this feel like a scary account takeover.

Visible promise:

> Memexai can read your selected playlists. It cannot upload, edit, delete, comment, or manage your channel.

States:

- Not connected: show `Connect YouTube`.
- Connected without refresh token: show `Reconnect for automatic sync`.
- Connected with read-only refresh grant: show success and continue.
- OAuth error: show short error and fallback to manual playlist URL.

### Step 3: Choose Capture Playlist

Best path after OAuth:

1. Backend calls YouTube Data API with the stored grant.
2. User sees their playlists.
3. User selects the playlist they use as their Memexai inbox.
4. App creates a `youtube_capture_sources` row.

Fallback path:

- Paste playlist URL manually.

Recommended guidance:

> Use a dedicated playlist like "Memexai Inbox." When you find a video worth keeping, save it there on YouTube.

Important scope note:

- With `youtube.readonly`, Memexai should not create the playlist for the user.
- If playlist creation is desired later, make it a separate advanced permission path because it needs broader YouTube scopes.

### Step 4: First Import

Screen purpose:

- Give the user first value quickly.
- Avoid starting with a massive channel or playlist ingest.

Default action:

- Sync the selected playlist.
- Queue the first eligible video, or up to 3 videos for users who explicitly choose "import a few."
- Show cost estimate and dedupe behavior before queueing more than one video.

Success state:

- Show the video title, status, and first useful action:
  - Search this video
  - Generate a study guide
  - Ask my agent to use this context

### Step 5: Agent Setup

Screen purpose:

- Make the MCP value real before the user leaves.
- Avoid burying the setup in Settings.

Prompt:

> Which agent do you want to connect first?

Options:

- Hermes on my machine
- Codex
- Claude Desktop
- ChatGPT or other MCP client
- Skip for now

Default token:

- `context:read`
- `overlay:write`

Optional toggle:

- `ingest:write`, off by default.

Show:

- MCP server URL
- env var name
- tailored config snippet
- first MCP calls:
  - `get_mcp_session`
  - `get_agent_quickstart`
  - `list_video_library`
  - `search_video_concepts`
  - `search_video_moments`

Success state:

> Your agent can now read your saved video context. Source transcripts stay read-only; agent notes go into your personal overlay.

### Exit

Final screen:

- Show one compact "what to do next" panel.
- Send them to the dashboard with their setup checklist still visible until completed.

Next actions:

- Save another video to the selected YouTube playlist.
- Run sync.
- Ask a question.
- Give the MCP setup bundle to an agent.

## Information Architecture

Add a first-run route or full-screen modal:

- `/setup`
- or an `OnboardingModal` rendered after auth when setup is incomplete.

Recommendation:

- Use a route for durability and deep-linking.
- Keep Settings as the permanent place to manage the same pieces later.
- Extract reusable sections instead of duplicating UI:
  - `YouTubeConnectionCard`
  - `CapturePlaylistPicker`
  - `AgentSetupCard`
  - `OnboardingProgress`

## Data Needed

Add onboarding state to the user profile:

- `onboarding_completed_at`
- `onboarding_skipped_at`
- `onboarding_step`
- `onboarding_state jsonb`

Derived completion can also be computed from:

- YouTube connection status exists.
- At least one active `youtube_capture_sources` row exists.
- At least one `user_videos` grant or queued ingestion job exists.
- At least one active MCP token exists.

Store explicit onboarding state anyway so users who intentionally skip do not get trapped in a repeated modal.

## Backend Needed

Already done:

- YouTube OAuth status/save/delete.
- Capture source create/list/sync.
- MCP token create/list/revoke.
- Profile onboarding state fields:
  - `onboarding_completed_at`
  - `onboarding_skipped_at`
  - `onboarding_step`
  - `onboarding_state jsonb`
- Profile onboarding endpoints:
  - `GET /api/onboarding/status`
  - `PATCH /api/onboarding/status`

Needed next:

- Refresh stored Google access tokens from `refresh_token_enc`.
- `GET /api/youtube/playlists` using YouTube Data API `playlists.list(mine=true)`.
- `POST /api/capture/sources/from-youtube-playlist` that creates a capture source from selected playlist metadata.
- Polished setup route/modal that calls the onboarding endpoints.

## Metrics

Track funnel events:

- Landing CTA clicked: start with YouTube vs sign in only.
- Google auth completed.
- YouTube grant saved.
- Playlist selected or pasted.
- Capture source created.
- First sync started.
- First video queued.
- First video searchable.
- MCP token created.
- MCP setup bundle copied.
- First search run.

Activation metrics:

- Time from signup to first video queued.
- Time from signup to first successful search.
- Percent of new users with a capture source.
- Percent of new users with an MCP token.
- Percent who skip YouTube but later connect it.

## Risks

Permission anxiety:

- Mitigation: explain read-only scope before consent and keep manual URL fallback.

Empty playlist:

- Mitigation: let users paste one video or pick a sample video after choosing an empty playlist.

Slow ingestion:

- Mitigation: queue one video first and show job state immediately.

Agent setup complexity:

- Mitigation: ask "which agent?" and show only one tailored snippet at a time.

Google workspace restrictions:

- Mitigation: support identity-only login plus manual playlist/video URL capture.

Scope creep:

- Mitigation: do not add playlist creation, browser extension, or broad YouTube write scopes to FTUE v1.

## Implementation Slices

### Slice 1: Setup Shell

- Add onboarding route/modal after auth.
- Add profile onboarding status fields and endpoints.
- Show checklist and allow skip/finish.

### Slice 2: YouTube Connection Step

- Reuse `connectYouTube`.
- Reuse YouTube OAuth status endpoint.
- Show connected, reconnect, and fallback states.

### Slice 3: Playlist Picker

- Add backend YouTube playlist listing with token refresh.
- Create capture source from selected playlist.
- Keep manual playlist URL fallback.

### Slice 4: First Import

- Trigger bounded sync from onboarding.
- Queue first eligible video.
- Show job state and first actions.

### Slice 5: Agent Setup

- Extract existing Settings MCP token UI into reusable card.
- Add agent selector.
- Create/copy one token/config bundle from onboarding.

### Slice 6: Dashboard Continuity

- Keep a compact setup checklist on the dashboard until all core activation steps are complete.
- Let users resume setup without losing progress.
