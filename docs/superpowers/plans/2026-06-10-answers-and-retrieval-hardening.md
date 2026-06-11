# Answers with Receipts + Retrieval Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the product deliver what the landing page promises — AI answers with clickable `[[clip_N]]` citations — and harden retrieval (soft intro filter, grouped results, empty states, committed search RPC).

**Architecture:** A new shared `backend/clip_selection.py` ranks candidate clips (prefer post-intro, backfill intro clips when short, suppress near-duplicates). A new `backend/answers.py` generates a cited answer from selected clips via `gemini-3.1-flash-lite`, failing safe to `""` so search never breaks on LLM errors. Both storage modes (`rag.py` pgvector, `rag_chroma.py` local) call these shared modules. Frontend renders the existing-but-unused `AnswerSection` above the player, groups sidebar clips by video, and adds a zero-results state. The hosted `search_chunks` RPC gets committed as migration 004.

**Tech Stack:** Python FastAPI, langchain-google-genai (`ChatGoogleGenerativeAI`), pgvector/ChromaDB, React 19 + Vitest, pytest.

**Verification baseline:** `python -m pytest tests/ -q` and `npm run verify` are green before starting; keep them green after every task. Dev servers: backend already on 8080 (local mode), frontend `npx vite --port 5173 --strictPort`.

---

### Task 1: Clip selection with soft intro filter

**Files:**

- Create: `backend/clip_selection.py`
- Test: `tests/test_clip_selection.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_clip_selection.py
from backend.clip_selection import select_clips


def make_clip(video_id: str, start: int, end: int) -> dict:
    return {
        "videoId": video_id,
        "title": f"video {video_id}",
        "channelName": "chan",
        "startSeconds": start,
        "endSeconds": end,
        "content": "text",
        "thumbnailUrl": "",
    }


def test_prefers_post_intro_clips():
    candidates = [make_clip("a", 30, 90), make_clip("a", 300, 360), make_clip("b", 500, 560)]
    result = select_clips(candidates, limit=2)
    assert [c["startSeconds"] for c in result] == [300, 500]


def test_backfills_intro_clips_when_short():
    candidates = [make_clip("a", 30, 90), make_clip("a", 300, 360)]
    result = select_clips(candidates, limit=3)
    # post-intro first, then intro backfill — never return fewer than available
    assert [c["startSeconds"] for c in result] == [300, 30]


def test_all_intro_still_returns_results():
    candidates = [make_clip("a", 0, 60), make_clip("a", 61, 110)]
    result = select_clips(candidates, limit=5)
    assert len(result) == 2


def test_suppresses_near_duplicates():
    # within 90s on the same video → duplicate
    candidates = [make_clip("a", 300, 360), make_clip("a", 350, 410), make_clip("a", 600, 660)]
    result = select_clips(candidates, limit=5)
    assert [c["startSeconds"] for c in result] == [300, 600]


def test_reassigns_sequential_ids():
    candidates = [make_clip("a", 30, 90), make_clip("a", 300, 360)]
    result = select_clips(candidates, limit=2)
    assert [c["id"] for c in result] == ["clip_0", "clip_1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_clip_selection.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.clip_selection'`

- [ ] **Step 3: Implement**

```python
# backend/clip_selection.py
"""Shared clip ranking: soft intro filter + near-duplicate suppression.

Both storage modes build raw candidate clips (similarity-ordered) and call
select_clips() to pick the final result set. Post-intro clips are preferred,
but intro clips backfill when there are not enough later matches — a short
video must never produce zero results.
"""

INTRO_SECONDS = 120
NEARBY_CHUNK_SECONDS = 90


def _is_near_existing(clip: dict, chosen: list[dict]) -> bool:
    for existing in chosen:
        if existing["videoId"] != clip["videoId"]:
            continue
        overlaps = (
            clip["startSeconds"] < existing["endSeconds"]
            and clip["endSeconds"] > existing["startSeconds"]
        )
        nearby = abs(clip["startSeconds"] - existing["startSeconds"]) < NEARBY_CHUNK_SECONDS
        if overlaps or nearby:
            return True
    return False


def select_clips(candidates: list[dict], limit: int, intro_seconds: int = INTRO_SECONDS) -> list[dict]:
    """Pick up to `limit` clips from similarity-ordered candidates.

    Two passes preserve similarity order within each tier: post-intro clips
    first, then intro clips as backfill. Near-duplicates (same video, within
    NEARBY_CHUNK_SECONDS or overlapping) are suppressed across both passes.
    Returns copies with sequential clip ids.
    """
    chosen: list[dict] = []

    def take(pool: list[dict]) -> None:
        for clip in pool:
            if len(chosen) >= limit:
                return
            if _is_near_existing(clip, chosen):
                continue
            chosen.append(clip)

    take([c for c in candidates if c["startSeconds"] >= intro_seconds])
    take([c for c in candidates if c["startSeconds"] < intro_seconds])

    return [{**clip, "id": f"clip_{i}"} for i, clip in enumerate(chosen)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_clip_selection.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```powershell
git add backend/clip_selection.py tests/test_clip_selection.py
git commit -m "feat: shared clip selection with soft intro filter"
```

---

### Task 2: Answer generation module

**Files:**

- Create: `backend/answers.py`
- Test: `tests/test_answers.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_answers.py
from backend import answers


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def __init__(self, reply: str):
        self.reply = reply
        self.last_prompt = None

    def invoke(self, prompt: str):
        self.last_prompt = prompt
        return FakeResponse(self.reply)


def make_clip(i: int, start: int = 200) -> dict:
    return {
        "id": f"clip_{i}",
        "videoId": f"vid{i}",
        "title": f"Video {i}",
        "channelName": "chan",
        "startSeconds": start,
        "endSeconds": start + 60,
        "content": f"transcript text {i}",
        "thumbnailUrl": "",
    }


def test_generates_answer_with_clip_context(monkeypatch):
    fake = FakeLLM("The speaker explains X [[clip_0]].")
    monkeypatch.setattr(answers, "_get_llm", lambda api_key: fake)
    result = answers.generate_answer("what is X", [make_clip(0)], api_key="k")
    assert result == "The speaker explains X [[clip_0]]."
    assert "transcript text 0" in fake.last_prompt
    assert "[clip_0]" in fake.last_prompt
    assert "what is X" in fake.last_prompt


def test_returns_empty_string_on_llm_failure(monkeypatch):
    def boom(api_key):
        raise RuntimeError("llm down")

    monkeypatch.setattr(answers, "_get_llm", boom)
    assert answers.generate_answer("q", [make_clip(0)], api_key="k") == ""


def test_returns_empty_string_for_no_clips():
    assert answers.generate_answer("q", [], api_key="k") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_answers.py -q`
Expected: FAIL with `ImportError: cannot import name 'answers'`

- [ ] **Step 3: Implement**

```python
# backend/answers.py
"""Cited answer generation over selected clips.

generate_answer() is failure-safe: any LLM error returns "" so search always
returns clips even when the answer step is unavailable.
"""

import os
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI

try:
    from .config import get_llm_model
except ImportError:
    from config import get_llm_model

MAX_CLIP_CHARS = 700

PROMPT_TEMPLATE = """You answer questions about video transcripts. Use ONLY the clips below.

Rules:
- Write 2-4 sentences, direct and concrete.
- After every claim, cite its supporting clip inline as [[clip_N]].
- Only cite clips that actually support the claim.
- If the clips do not answer the question, reply exactly: I couldn't find this in your indexed videos.

Question: {query}

Clips:
{clips}

Answer:"""


def _format_timestamp(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _get_llm(api_key: Optional[str]) -> ChatGoogleGenerativeAI:
    key_to_use = api_key or os.getenv("GEMINI_API_KEY")
    if not key_to_use:
        raise ValueError("No API key available for answer generation")
    return ChatGoogleGenerativeAI(
        model=get_llm_model(),
        google_api_key=key_to_use,
        temperature=0.2,
        max_output_tokens=512,
    )


def generate_answer(query: str, clips: list[dict], api_key: Optional[str] = None) -> str:
    """Generate a short cited answer from selected clips. Returns "" on any failure."""
    if not clips:
        return ""

    clip_lines = []
    for clip in clips:
        content = " ".join(clip["content"].split())[:MAX_CLIP_CHARS]
        clip_lines.append(
            f'[{clip["id"]}] "{clip["title"]}" at {_format_timestamp(clip["startSeconds"])}: {content}'
        )

    prompt = PROMPT_TEMPLATE.format(query=query, clips="\n".join(clip_lines))

    try:
        llm = _get_llm(api_key)
        response = llm.invoke(prompt)
        return (response.content or "").strip()
    except Exception as exc:  # noqa: BLE001 — answer must never break search
        print(f"[ANSWERS] Generation failed, returning clips only: {exc}")
        return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_answers.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```powershell
git add backend/answers.py tests/test_answers.py
git commit -m "feat: cited answer generation with failure-safe fallback"
```

---

### Task 3: Wire selection + answers into local mode (rag_chroma)

**Files:**

- Modify: `backend/rag_chroma.py:158-238` (the `search()` function result assembly)

- [ ] **Step 1: Replace the hard intro filter with shared selection + answer**

In `backend/rag_chroma.py`:

- Change retriever `k` from `limit * 2` to `limit * 4` (line ~180).
- Replace the loop at lines ~196-233 (SKIP_INTRO_SECONDS filter, `_is_near_existing_clip`, manual `clip_index`) with: build ALL candidates (no filtering, no id assignment beyond placeholder), then:

```python
    candidates: list[VideoClip] = []
    for doc in docs:
        meta = doc.metadata
        candidates.append(
            {
                "id": "clip_pending",
                "videoId": meta.get("video_id", ""),
                "title": meta.get("title", "Unknown"),
                "channelName": meta.get("channel_name", "Unknown"),
                "startSeconds": int(meta.get("start_seconds", 0)),
                "endSeconds": int(meta.get("end_seconds", 0)),
                "content": doc.page_content,
                "thumbnailUrl": meta.get("thumbnail_url", ""),
                "matchSnippet": _match_snippet(doc.page_content),
                "relevanceReason": "Semantic match in the transcript near this timestamp.",
            }
        )

    clips = select_clips(candidates, limit)
    answer = generate_answer(query, clips, api_key)

    return {
        "answer": answer,
        "relevantClips": clips,
    }
```

- Add imports at top (mirror the existing try/except relative-import pattern in the file):

```python
try:
    from .answers import generate_answer
    from .clip_selection import select_clips
except ImportError:
    from answers import generate_answer
    from clip_selection import select_clips
```

- Delete the now-unused local `_is_near_existing_clip` helper and `SKIP_INTRO_SECONDS` constant if nothing else references them (grep the file first).

- [ ] **Step 2: Verify**

Run: `python -m pytest tests/ -q && python -c "import backend.rag_chroma"`
Expected: all pass, clean import

- [ ] **Step 3: Commit**

```powershell
git add backend/rag_chroma.py
git commit -m "feat: cited answers + soft intro filter in local search"
```

---

### Task 4: Wire selection + answers into hosted mode (rag.py)

**Files:**

- Modify: `backend/rag.py:85-159` (`search_pg`)

- [ ] **Step 1: Move filtering into Python and add the answer**

In `search_pg`:

- Change the RPC call's `"min_start_seconds": 120` to `"min_start_seconds": 0` (soft filtering now happens in `select_clips`; the RPC param remains for API compatibility).
- Replace the result-mapping loop (lines ~131-152) with: build ALL rows into candidates with `"id": "clip_pending"` (same fields as today), then:

```python
    clips = select_clips(candidates, limit)
    answer = generate_answer(query, clips, api_key)

    print(f"[SEARCH_PG] Returning {len(clips)} clips (answer: {len(answer)} chars)")

    return {
        "answer": answer,
        "relevantClips": clips,
    }
```

- Add imports (same try/except pattern used at rag.py:19-24):

```python
try:
    from .answers import generate_answer
    from .clip_selection import select_clips
except ImportError:
    from answers import generate_answer
    from clip_selection import select_clips
```

- Delete the now-unused `_is_near_existing_clip` and `NEARBY_CHUNK_SECONDS` from rag.py if nothing else in the file uses them (grep first).

- [ ] **Step 2: Verify**

Run: `python -m pytest tests/ -q && python -c "import backend.rag"`
Expected: all pass, clean import

- [ ] **Step 3: Commit**

```powershell
git add backend/rag.py
git commit -m "feat: cited answers + soft intro filter in hosted search"
```

---

### Task 5: Commit the search_chunks RPC as a migration

**Files:**

- Create: `backend/supabase/migrations/004_search_chunks_rpc.sql`

- [ ] **Step 1: Write the migration**

Signature must match the rag.py call exactly: `(query_embedding, match_user_id, match_limit, min_start_seconds)`; returns the columns search_pg reads (`youtube_video_id, title, channel_name, start_seconds, end_seconds, content, thumbnail_url, similarity`); scoped via user_channels.

```sql
-- 004_search_chunks_rpc.sql
-- User-scoped vector search over chunks. Codifies the RPC the hosted app
-- depends on so fresh deploys do not silently lose per-user scoping.

CREATE OR REPLACE FUNCTION search_chunks(
  query_embedding VECTOR(768),
  match_user_id UUID,
  match_limit INT DEFAULT 20,
  min_start_seconds INT DEFAULT 0
)
RETURNS TABLE (
  youtube_video_id TEXT,
  title TEXT,
  channel_name TEXT,
  start_seconds INT,
  end_seconds INT,
  content TEXT,
  thumbnail_url TEXT,
  similarity FLOAT
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    v.youtube_video_id,
    v.title,
    ch.name AS channel_name,
    c.start_seconds,
    c.end_seconds,
    c.content,
    v.thumbnail_url,
    1 - (c.embedding <=> query_embedding) AS similarity
  FROM chunks c
  JOIN videos v ON v.id = c.video_id
  JOIN channels ch ON ch.id = v.channel_id
  JOIN user_channels uc ON uc.channel_id = ch.id
  WHERE uc.user_id = match_user_id
    AND c.start_seconds >= min_start_seconds
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_limit;
$$;
```

- [ ] **Step 2: Verify against the live project (best effort)**

Run: `npx supabase migration list` (already linked). If the CLI session is authenticated, also run `npx supabase db push --dry-run` and confirm only 004 is pending. If auth is unavailable, leave a note in tasks/todo.md to apply 004 before the next deploy and reconcile with the live function definition.

- [ ] **Step 3: Commit**

```powershell
git add backend/supabase/migrations/004_search_chunks_rpc.sql
git commit -m "feat: commit search_chunks RPC as migration"
```

---

### Task 6: Frontend — answer card + zero-results state

**Files:**

- Modify: `src/App.tsx` (results view; AnswerSection import)
- Test: existing suites stay green (`npm test`)

- [ ] **Step 1: Import and render AnswerSection**

In `src/App.tsx` add `import { AnswerSection } from './components/AnswerSection';`. In the Search Results View main column, render the answer ABOVE the player when present:

```tsx
{/* Main Content: Answer + Video + Transcript */}
<div className="flex-1 max-w-4xl">
  {searchState.answer && (
    <div className="mb-5">
      <AnswerSection
        answer={searchState.answer}
        clips={searchState.relevantClips}
        onCitationClick={handleCitationClick}
      />
    </div>
  )}
  {/* Video Player */}
  ...existing player block unchanged...
```

- [ ] **Step 2: Add the zero-results state**

Inside the results area, when the search completed but returned nothing, replace the two-column layout with an empty-state card. Wrap the existing `<div className="flex flex-col-reverse gap-6 md:flex-row">` in a conditional:

```tsx
{
  searchState.status === 'complete' && searchState.relevantClips.length === 0 ? (
    <div className="card mx-auto max-w-xl p-8 text-center">
      <h2 className="font-serif text-3xl font-medium text-ink">No moments found</h2>
      <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-bark">
        Nothing in your library matched that description. Try different wording, or index more
        videos to widen the search.
      </p>
      <button onClick={() => setMode('unified')} className="btn btn-primary mt-6">
        Try another search
      </button>
    </div>
  ) : (
    <existing two-column layout />
  );
}
```

- [ ] **Step 3: Verify**

Run: `npm run typecheck && npm test`
Expected: all green (existing tests assert text/roles that are unchanged)

- [ ] **Step 4: Commit**

```powershell
git add src/App.tsx
git commit -m "feat: render cited answer card and zero-results state"
```

---

### Task 7: Frontend — group sidebar clips by video

**Files:**

- Create: `src/lib/clips.ts`
- Create: `src/lib/clips.test.ts`
- Modify: `src/App.tsx` (sidebar render)

- [ ] **Step 1: Write the failing test**

```ts
// src/lib/clips.test.ts
import { describe, expect, it } from 'vitest';
import { groupClipsByVideo } from './clips';
import type { VideoClip } from '../types';

const clip = (id: string, videoId: string, start: number): VideoClip =>
  ({
    id,
    videoId,
    title: `t-${videoId}`,
    channelName: 'c',
    startSeconds: start,
    endSeconds: start + 60,
    content: '',
    thumbnailUrl: `thumb-${videoId}`,
  }) as VideoClip;

describe('groupClipsByVideo', () => {
  it('groups clips under one entry per video, preserving first-seen order', () => {
    const groups = groupClipsByVideo([
      clip('a', 'v1', 10),
      clip('b', 'v2', 20),
      clip('c', 'v1', 99),
    ]);
    expect(groups.map((g) => g.videoId)).toEqual(['v1', 'v2']);
    expect(groups[0].clips.map((c) => c.id)).toEqual(['a', 'c']);
    expect(groups[0].title).toBe('t-v1');
  });

  it('returns empty array for no clips', () => {
    expect(groupClipsByVideo([])).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/lib/clips.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Implement**

```ts
// src/lib/clips.ts
import type { VideoClip } from '../types';

export interface VideoClipGroup {
  videoId: string;
  title: string;
  channelName: string;
  thumbnailUrl: string;
  clips: VideoClip[];
}

export function groupClipsByVideo(clips: VideoClip[]): VideoClipGroup[] {
  const groups = new Map<string, VideoClipGroup>();
  for (const clip of clips) {
    const existing = groups.get(clip.videoId);
    if (existing) {
      existing.clips.push(clip);
    } else {
      groups.set(clip.videoId, {
        videoId: clip.videoId,
        title: clip.title,
        channelName: clip.channelName,
        thumbnailUrl: clip.thumbnailUrl,
        clips: [clip],
      });
    }
  }
  return [...groups.values()];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/lib/clips.test.ts`
Expected: 2 passed

- [ ] **Step 5: Replace the sidebar clip list with grouped rendering**

In `src/App.tsx`, import `groupClipsByVideo`, and replace the `searchState.relevantClips.map((clip) => ...)` sidebar block with one card per video group: thumbnail + title once, then a wrapping row of timestamp chips (one per clip; active clip gets the filled style). Keep the horizontal-scroll-on-mobile container classes unchanged.

```tsx
{
  groupClipsByVideo(searchState.relevantClips).map((group) => (
    <div key={group.videoId} className="card w-56 flex-shrink-0 overflow-hidden p-2 md:w-auto">
      <button
        onClick={() => handleCitationClick(group.clips[0])}
        className="block w-full text-left"
      >
        {group.thumbnailUrl && (
          <img src={group.thumbnailUrl} className="h-auto w-full rounded-lg" alt="" />
        )}
        <p className="mt-2 line-clamp-2 text-xs font-semibold text-ink">{group.title}</p>
      </button>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {group.clips.map((clip) => (
          <button
            key={clip.id}
            onClick={() => handleCitationClick(clip)}
            className={`rounded-full px-2 py-0.5 font-mono text-xs font-medium transition-colors ${
              activeClip?.id === clip.id
                ? 'bg-rose-deep text-cream'
                : 'bg-petal/60 text-rose-deep hover:bg-petal'
            }`}
          >
            {formatTime(clip.startSeconds)}
          </button>
        ))}
      </div>
    </div>
  ));
}
```

(The per-clip copy-link icon is dropped from the sidebar; Copy Link remains on the active-clip player card. Remove the now-unused `ring-2` active-card styling.)

- [ ] **Step 6: Verify**

Run: `npm run typecheck && npm test`
Expected: all green

- [ ] **Step 7: Commit**

```powershell
git add src/lib/clips.ts src/lib/clips.test.ts src/App.tsx
git commit -m "feat: group search results by video with timestamp chips"
```

---

### Task 8: Docs + landing alignment

**Files:**

- Modify: `CLAUDE.md` (stale references)
- Modify: `src/components/LandingPage.tsx` (vignette wording only if needed)

- [ ] **Step 1: Update CLAUDE.md**

Fix stale facts: AI model line (`text-embedding-004`/`gemini-2.0-flash` → `gemini-embedding-001` 768-dim + `gemini-3.1-flash-lite`), citation-system paragraph (now real again via `backend/answers.py` + `AnswerSection`), Key Files table (add `backend/answers.py`, `backend/clip_selection.py`), Tunable Constants (chunking now sentence-aware 60s/12s overlap in `backend/youtube_utils.py`; intro filter `backend/clip_selection.py` INTRO_SECONDS; prompt in `backend/answers.py` PROMPT_TEMPLATE).

- [ ] **Step 2: Re-read the landing vignette against the real answer format**

`MomentVignette` in `src/components/LandingPage.tsx` shows: question → short answer → timestamp chips. That now matches the real product (AnswerSection renders the same chips). Only change wording if the rendered E2E answer reads materially differently; otherwise no code change.

- [ ] **Step 3: Commit**

```powershell
git add CLAUDE.md src/components/LandingPage.tsx
git commit -m "docs: align CLAUDE.md and landing copy with cited answers"
```

---

### Task 9: End-to-end verification

**Files:**

- Modify: `scripts/dev-e2e.mjs` (assert the answer card appears)

- [ ] **Step 1: Extend the E2E to assert the answer**

After the results-rendered check in `scripts/dev-e2e.mjs`, add:

```js
const answerCard = await page.getByText('Answer with receipts').count();
console.log('answer card present:', answerCard > 0);
const citationChips = await page.locator('p button:has(svg)').count();
console.log('citation chips:', citationChips);
```

- [ ] **Step 2: Run the live E2E**

Backend on 8080 (local mode) and frontend on 5173 must be running.
Run: `node scripts/dev-e2e.mjs`
Expected: `answer card present: true`, `citation chips: >= 1`, search lands on a sensible moment. Read `screenshots/e2e-3-results.png` and visually confirm the answer card + grouped sidebar.

- [ ] **Step 3: Full verification**

Run: `python -m pytest tests/ -q` then `npm run verify`
Expected: all green

- [ ] **Step 4: Commit**

```powershell
git add scripts/dev-e2e.mjs
git commit -m "test: assert cited answer in dev E2E"
```
