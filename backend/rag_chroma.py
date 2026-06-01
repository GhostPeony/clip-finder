"""
rag.py - RAG Search Engine for YouTube Content

Retrieves relevant video clips from ChromaDB and generates answers with citations
using Gemini 2.0 Flash.

Key Features:
- Semantic search across all indexed video transcripts
- Returns timestamped deep links to exact video moments
- Uses [[clip_N]] citation format for frontend parsing
- LCEL chain for clean, composable architecture

Updated: 2025-12-28
LangChain Google Package: langchain-google-genai>=4.0.0 (consolidated SDK)
"""

import os
from typing import TypedDict
from dotenv import load_dotenv

from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

try:
    from .config import get_embedding_dimensions, get_embedding_model, get_llm_model
except ImportError:
    from config import get_embedding_dimensions, get_embedding_model, get_llm_model

# Load environment variables from parent directory (where .env.local lives)
env_path = os.path.join(os.path.dirname(__file__), '..', '.env.local')
load_dotenv(env_path)

# Configuration - use absolute path to avoid issues with working directory
DB_PATH = os.path.join(os.path.dirname(__file__), "channel_chroma_db")
EMBEDDING_MODEL = get_embedding_model()
LLM_MODEL = get_llm_model()
TOP_K_RESULTS = 5  # Number of relevant clips to retrieve
NEARBY_CHUNK_SECONDS = 90


class VideoClip(TypedDict):
    """Video clip structure matching frontend expectations."""
    id: str
    videoId: str
    title: str
    channelName: str
    startSeconds: int
    endSeconds: int
    content: str
    thumbnailUrl: str
    matchSnippet: str
    relevanceReason: str


class SearchResult(TypedDict):
    """Search result structure matching frontend expectations."""
    answer: str
    relevantClips: list[VideoClip]


# Cache for singleton instances (avoid recreating API clients)
_embeddings_instance = None
_embeddings_api_key = None  # Track key for embeddings
_llm_instance = None
_llm_api_key = None  # Track key for LLM
_vectorstore_instance = None
_vectorstore_api_key = None  # Track key for vectorstore


def get_embeddings(api_key: str = None) -> GoogleGenerativeAIEmbeddings:
    """Get embeddings instance with API key from parameter or environment."""
    global _embeddings_instance, _embeddings_api_key

    key_to_use = api_key or os.getenv("GEMINI_API_KEY")
    if not key_to_use or key_to_use == "PLACEHOLDER_API_KEY":
        raise ValueError("No API key provided. Set GEMINI_API_KEY or provide via header.")

    # Reuse existing instance if same key (compare first 10 chars to handle minor differences)
    if _embeddings_instance is not None and _embeddings_api_key and key_to_use:
        if _embeddings_api_key[:10] == key_to_use[:10]:
            return _embeddings_instance

    print(f"[RAG] Creating new embeddings instance (key: {key_to_use[:8]}...)")
    _embeddings_api_key = key_to_use
    _embeddings_instance = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=key_to_use,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=get_embedding_dimensions(),
    )
    return _embeddings_instance


def get_llm(api_key: str = None) -> ChatGoogleGenerativeAI:
    """Get LLM instance with API key from parameter or environment."""
    global _llm_instance, _llm_api_key

    key_to_use = api_key or os.getenv("GEMINI_API_KEY")
    if not key_to_use or key_to_use == "PLACEHOLDER_API_KEY":
        raise ValueError("No API key provided. Set GEMINI_API_KEY or provide via header.")

    # Reuse existing instance if same key
    if _llm_instance is not None and _llm_api_key and key_to_use:
        if _llm_api_key[:10] == key_to_use[:10]:
            return _llm_instance

    print(f"[RAG] Creating new LLM instance (key: {key_to_use[:8]}...)")
    _llm_api_key = key_to_use
    _llm_instance = ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=key_to_use,
        temperature=0.3,
    )
    return _llm_instance


def get_vectorstore(api_key: str = None) -> Chroma:
    """Get ChromaDB vector store with optional API key for embeddings."""
    global _vectorstore_instance, _vectorstore_api_key

    key_to_use = api_key or os.getenv("GEMINI_API_KEY")

    # Reuse existing instance if same key
    if _vectorstore_instance is not None and _vectorstore_api_key and key_to_use:
        if _vectorstore_api_key[:10] == key_to_use[:10]:
            return _vectorstore_instance

    print(f"[RAG] Creating new vectorstore instance (key: {key_to_use[:8] if key_to_use else 'None'}...)")
    _vectorstore_api_key = key_to_use
    _vectorstore_instance = Chroma(
        persist_directory=DB_PATH,
        embedding_function=get_embeddings(api_key),
        collection_name="video_knowledge"
    )
    return _vectorstore_instance


def _is_near_existing_clip(video_id: str, start_seconds: int, end_seconds: int, clips: list[VideoClip]) -> bool:
    for clip in clips:
        if clip["videoId"] != video_id:
            continue
        overlaps = start_seconds < clip["endSeconds"] and end_seconds > clip["startSeconds"]
        nearby = abs(start_seconds - clip["startSeconds"]) < NEARBY_CHUNK_SECONDS
        if overlaps or nearby:
            return True
    return False


def _match_snippet(content: str, max_length: int = 240) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 1].rstrip()}…"


def search(query: str, api_key: str = None, limit: int = 5) -> SearchResult:
    """
    Search the indexed videos and return relevant clips with transcripts.

    Args:
        query: The user's question
        api_key: Optional API key override (for BYOK)
        limit: Number of results to return (default 5)

    Returns:
        SearchResult with clips containing their transcript content
    """
    print(f"[SEARCH] Starting search for: {query[:50]}... (limit={limit})")

    # Check if database exists
    print(f"[SEARCH] Getting vectorstore...")
    vectorstore = get_vectorstore(api_key)

    # Get retriever - request extra results to compensate for intro filtering
    print(f"[SEARCH] Creating retriever...")
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": limit * 2}  # Get extra to filter from
    )

    # Retrieve relevant documents
    print(f"[SEARCH] Invoking retriever (this calls embeddings API once)...")
    docs = retriever.invoke(query)
    print(f"[SEARCH] Found {len(docs)} documents")

    if not docs:
        return {
            "answer": "",  # No AI overview needed
            "relevantClips": []
        }

    # Build clips list with transcript content
    # Filter out intro clips (first 2 minutes) - they're often teasers, not the real content
    SKIP_INTRO_SECONDS = 120
    clips: list[VideoClip] = []

    clip_index = 0
    for doc in docs:
        if len(clips) >= limit:
            break  # We have enough results

        meta = doc.metadata
        start_seconds = int(meta.get("start_seconds", 0))
        end_seconds = int(meta.get("end_seconds", 0))
        video_id = meta.get("video_id", "")

        # Skip clips from the intro section
        if start_seconds < SKIP_INTRO_SECONDS:
            print(f"[SEARCH] Skipping intro clip at {start_seconds}s")
            continue
        if _is_near_existing_clip(video_id, start_seconds, end_seconds, clips):
            print(f"[SEARCH] Skipping nearby duplicate clip at {start_seconds}s")
            continue

        clip_id = f"clip_{clip_index}"
        clip_index += 1

        # Create clip object for frontend with full transcript content
        clip: VideoClip = {
            "id": clip_id,
            "videoId": video_id,
            "title": meta.get("title", "Unknown"),
            "channelName": meta.get("channel_name", "Unknown"),
            "startSeconds": start_seconds,
            "endSeconds": end_seconds,
            "content": doc.page_content,  # Full transcript, not truncated
            "thumbnailUrl": meta.get("thumbnail_url", ""),
            "matchSnippet": _match_snippet(doc.page_content),
            "relevanceReason": "Semantic match in the transcript near this timestamp.",
        }
        clips.append(clip)

    return {
        "answer": "",  # Empty - frontend will show transcript content directly
        "relevantClips": clips
    }


def _format_time(seconds: int) -> str:
    """Format seconds as MM:SS."""
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"


# For testing/standalone usage
if __name__ == "__main__":
    import json

    print("SearchTube RAG Search Test\n")

    while True:
        query = input("\nEnter your question (or 'quit' to exit): ").strip()
        if query.lower() in ('quit', 'exit', 'q'):
            break

        print("\n🔍 Searching...\n")
        result = search(query)

        print("=" * 60)
        print("ANSWER:")
        print("=" * 60)
        print(result["answer"])

        print("\n" + "=" * 60)
        print("RELEVANT CLIPS:")
        print("=" * 60)
        for clip in result["relevantClips"]:
            timestamp = _format_time(clip["startSeconds"])
            link = f"https://youtu.be/{clip['videoId']}?t={clip['startSeconds']}"
            print(f"\n[{clip['id']}] {clip['title']}")
            print(f"    Time: {timestamp} | {link}")
            print(f"    Preview: {clip['content'][:100]}...")
