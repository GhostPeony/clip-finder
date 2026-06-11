# Safety And Ethics

This product indexes YouTube transcripts and returns timestamped retrieval results. The engineering defaults should protect users, creators, and the hosted operator.

## Product Principles

- Index only content a user intentionally submits.
- Show timestamp links so results are inspectable against the source video.
- Treat generated answers as summaries, not authority.
- Keep server-side Gemini credentials off the client.
- Keep Supabase service-role credentials backend-only.
- Store user-provided API keys only when BYOK is deliberately enabled, and use them only
  for that user's AI requests.
- Log enough ingestion detail to explain failures without storing unnecessary sensitive data.

## Data Handling

- Transcript chunks are stored to support search and timestamp retrieval.
- User access to library, transcript, usage, and ingestion job data must remain scoped by authenticated user.
- Deletion should remove videos and transcript chunks from the searchable store.
- Job events may include URLs and skip reasons; do not add raw secrets or authorization headers to job logs.

## AI And Retrieval Behavior

- Retrieval must include citations or timestamp links when making claims about video content.
- Model or embedding changes should go through the eval harness before becoming defaults.
- Search quality changes should be measured with recall and MRR fixtures, not only subjective examples.

## Hosted Cost And Abuse Guardrails

- Enforce hosted monthly search quotas for server-key usage.
- Enforce hosted video and transcript-hour library caps even when a user brings their own key.
- Keep CORS restricted to production and preview origins.
- Add durable background ingestion before public imports at scale.
- Monitor failed, skipped, and partial ingestion jobs for abuse or provider blocking.
