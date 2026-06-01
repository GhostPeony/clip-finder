"""
ingest.py - Smart YouTube Channel Indexer

Uses scrapetube to discover videos and LangChain to create searchable embeddings.
Yields progress messages for SSE streaming to the frontend.

Key Features:
- No YouTube API key required (uses scrapetube)
- 60-second chunks with timestamps for pinpoint accuracy
- Smart skip: Only indexes new videos on re-runs
- Uses the configured Gemini embedding model (default: gemini-embedding-001)

Updated: 2025-12-28
LangChain Google Package: langchain-google-genai>=4.0.0 (consolidated SDK)
"""

import os
import time
from typing import Generator, Optional
from dotenv import load_dotenv

import scrapetube
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

try:
    from .config import get_embedding_dimensions, get_embedding_model
    from .youtube_utils import get_transcript_chunks as get_shared_transcript_chunks
except ImportError:
    from config import get_embedding_dimensions, get_embedding_model
    from youtube_utils import get_transcript_chunks as get_shared_transcript_chunks

# Load environment variables from parent directory (where .env.local lives)
env_path = os.path.join(os.path.dirname(__file__), '..', '.env.local')
load_dotenv(env_path)

# Configuration - use absolute path to avoid issues with working directory
DB_PATH = os.path.join(os.path.dirname(__file__), "channel_chroma_db")
CHUNK_SIZE_SECONDS = 60  # 60s chunks for pinpoint accuracy
EMBEDDING_MODEL = get_embedding_model()

# Cache for singleton instances (avoid recreating API clients)
_embeddings_instance = None
_vectorstore_instance = None
_current_api_key = None  # Track which API key is being used
_vectorstore_api_key = None


def get_embeddings(api_key: str = None) -> GoogleGenerativeAIEmbeddings:
    """Get embeddings instance with API key from parameter or environment."""
    global _embeddings_instance, _current_api_key

    # Determine which API key to use
    key_to_use = api_key or os.getenv("GEMINI_API_KEY")
    if not key_to_use or key_to_use == "PLACEHOLDER_API_KEY":
        raise ValueError("No API key provided. Set GEMINI_API_KEY in .env.local or provide via header.")

    # If we have a cached instance with the same key, return it
    if _embeddings_instance is not None and _current_api_key == key_to_use:
        return _embeddings_instance

    # Create new instance with the provided key
    _current_api_key = key_to_use
    _embeddings_instance = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=key_to_use,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=get_embedding_dimensions(),
    )
    return _embeddings_instance


def get_vectorstore(api_key: str = None) -> Chroma:
    """Get cached ChromaDB vector store."""
    global _vectorstore_instance, _vectorstore_api_key

    key_to_use = api_key or os.getenv("GEMINI_API_KEY")

    if _vectorstore_instance is not None and _vectorstore_api_key == key_to_use:
        return _vectorstore_instance

    _vectorstore_api_key = key_to_use
    _vectorstore_instance = Chroma(
        persist_directory=DB_PATH,
        embedding_function=get_embeddings(api_key),
        collection_name="video_knowledge"
    )
    return _vectorstore_instance


def get_indexed_video_ids(api_key: str = None) -> set:
    """Get set of video IDs already in the database."""
    try:
        vectorstore = get_vectorstore(api_key)
        existing = vectorstore.get()
        indexed_ids = set()
        if existing and existing.get('metadatas'):
            for meta in existing['metadatas']:
                if meta and 'video_id' in meta:
                    indexed_ids.add(meta['video_id'])
        return indexed_ids
    except Exception:
        return set()


def get_library() -> dict:
    """
    Get all indexed videos organized by channel.

    Returns:
        Dict with channels list, total videos, and total clips
    """
    try:
        vectorstore = get_vectorstore()
        existing = vectorstore.get()

        if not existing or not existing.get('metadatas'):
            return {"channels": [], "totalVideos": 0, "totalClips": 0}

        # Group clips by channel and video
        channels_data: dict = {}

        for meta in existing['metadatas']:
            if not meta:
                continue

            channel_name = meta.get('channel_name', 'Unknown Channel')
            video_id = meta.get('video_id', '')

            if not video_id:
                continue

            # Initialize channel if needed
            if channel_name not in channels_data:
                channels_data[channel_name] = {'videos': {}}

            # Initialize video if needed
            if video_id not in channels_data[channel_name]['videos']:
                channels_data[channel_name]['videos'][video_id] = {
                    'videoId': video_id,
                    'title': meta.get('title', f'Video {video_id}'),
                    'thumbnailUrl': meta.get('thumbnail_url', f'https://img.youtube.com/vi/{video_id}/mqdefault.jpg'),
                    'clipCount': 0,
                    'indexedAt': meta.get('indexed_at')  # Unix timestamp, None for old entries
                }

            # Increment clip count
            channels_data[channel_name]['videos'][video_id]['clipCount'] += 1

        # Convert to list format
        channels_list = []
        total_videos = 0
        total_clips = len(existing['metadatas'])

        for channel_name, data in sorted(channels_data.items()):
            videos = list(data['videos'].values())
            total_videos += len(videos)
            channels_list.append({
                'name': channel_name,
                'videoCount': len(videos),
                'videos': videos
            })

        return {
            "channels": channels_list,
            "totalVideos": total_videos,
            "totalClips": total_clips
        }

    except Exception as e:
        print(f"Error getting library: {e}")
        return {"channels": [], "totalVideos": 0, "totalClips": 0}


def rename_channel(old_name: str, new_name: str) -> dict:
    """
    Rename a channel in the database by updating metadata on all its clips.

    Args:
        old_name: Current channel name to find
        new_name: New channel name to set

    Returns:
        Dict with success status and count of updated documents
    """
    global _vectorstore_instance

    try:
        vectorstore = get_vectorstore()
        existing = vectorstore.get()

        if not existing or not existing.get('ids'):
            return {"success": False, "error": "Database is empty", "updatedClips": 0}

        # Find all document IDs that belong to this channel
        ids_to_update = []
        metadatas_to_update = []

        for i, meta in enumerate(existing['metadatas']):
            if meta and meta.get('channel_name') == old_name:
                ids_to_update.append(existing['ids'][i])
                # Copy metadata and update channel_name
                updated_meta = dict(meta)
                updated_meta['channel_name'] = new_name
                metadatas_to_update.append(updated_meta)

        if not ids_to_update:
            return {"success": False, "error": f"Channel '{old_name}' not found", "updatedClips": 0}

        # Use the underlying ChromaDB collection to update metadata
        collection = vectorstore._collection
        collection.update(
            ids=ids_to_update,
            metadatas=metadatas_to_update
        )

        # Clear the cached vectorstore to force refresh
        _vectorstore_instance = None

        return {"success": True, "updatedClips": len(ids_to_update), "oldName": old_name, "newName": new_name}

    except Exception as e:
        return {"success": False, "error": str(e), "updatedClips": 0}


def get_video_transcript(video_id: str) -> dict:
    """
    Get all transcript chunks for a specific video, ordered by timestamp.

    Args:
        video_id: YouTube video ID

    Returns:
        Dict with video info and ordered transcript chunks
    """
    try:
        vectorstore = get_vectorstore()
        existing = vectorstore.get()

        if not existing or not existing.get('metadatas'):
            return {"success": False, "error": "Database is empty", "chunks": []}

        # Find all chunks for this video
        chunks = []
        video_title = None
        channel_name = None

        for i, meta in enumerate(existing['metadatas']):
            if meta and meta.get('video_id') == video_id:
                if video_title is None:
                    video_title = meta.get('title', f'Video {video_id}')
                    channel_name = meta.get('channel_name', 'Unknown Channel')

                chunks.append({
                    'text': existing['documents'][i] if existing.get('documents') else '',
                    'start_seconds': meta.get('start_seconds', 0),
                    'end_seconds': meta.get('end_seconds', 0),
                })

        if not chunks:
            return {"success": False, "error": "Video not found", "chunks": []}

        # Sort by start time
        chunks.sort(key=lambda c: c['start_seconds'])

        return {
            "success": True,
            "videoId": video_id,
            "title": video_title,
            "channelName": channel_name,
            "chunks": chunks
        }

    except Exception as e:
        return {"success": False, "error": str(e), "chunks": []}


def delete_video(video_id: str) -> dict:
    """
    Delete a video and all its clips from the database.

    Args:
        video_id: YouTube video ID to delete

    Returns:
        Dict with success status and deleted clip count
    """
    global _vectorstore_instance

    try:
        vectorstore = get_vectorstore()
        existing = vectorstore.get()

        if not existing or not existing.get('ids'):
            return {"success": False, "error": "Database is empty", "deletedClips": 0}

        # Find all document IDs that belong to this video
        ids_to_delete = []
        for i, meta in enumerate(existing['metadatas']):
            if meta and meta.get('video_id') == video_id:
                ids_to_delete.append(existing['ids'][i])

        if not ids_to_delete:
            return {"success": False, "error": "Video not found", "deletedClips": 0}

        # Delete from ChromaDB
        vectorstore.delete(ids=ids_to_delete)

        # Clear the cached vectorstore to force refresh
        _vectorstore_instance = None

        return {"success": True, "deletedClips": len(ids_to_delete)}

    except Exception as e:
        return {"success": False, "error": str(e), "deletedClips": 0}


def extract_video_title(video: dict) -> str:
    """Safely extract video title from scrapetube response."""
    try:
        # scrapetube returns nested structure for title
        title_obj = video.get('title', {})
        if isinstance(title_obj, dict):
            runs = title_obj.get('runs', [])
            if runs and len(runs) > 0:
                return runs[0].get('text', 'Unknown Title')
        return str(title_obj) if title_obj else 'Unknown Title'
    except Exception:
        return 'Unknown Title'


def extract_channel_name(video: dict) -> str:
    """Safely extract channel name from scrapetube response."""
    try:
        # Try ownerText (channel/playlist responses)
        owner = video.get('ownerText', {})
        if isinstance(owner, dict):
            runs = owner.get('runs', [])
            if runs and len(runs) > 0:
                return runs[0].get('text', 'Unknown Channel')

        # Try longBylineText (some video responses)
        byline = video.get('longBylineText', {})
        if isinstance(byline, dict):
            runs = byline.get('runs', [])
            if runs and len(runs) > 0:
                return runs[0].get('text', 'Unknown Channel')

        # Try shortBylineText
        short_byline = video.get('shortBylineText', {})
        if isinstance(short_byline, dict):
            runs = short_byline.get('runs', [])
            if runs and len(runs) > 0:
                return runs[0].get('text', 'Unknown Channel')

        return 'Unknown Channel'
    except Exception:
        return 'Unknown Channel'


def fetch_video_metadata(video_id: str) -> tuple[str, str]:
    """
    Fetch video title and channel name using YouTube oEmbed API.
    This is more reliable for single videos than scrapetube.get_video().

    Returns:
        Tuple of (title, channel_name)
    """
    import urllib.request
    import json

    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            title = data.get('title', f'Video {video_id}')
            channel = data.get('author_name', 'Unknown Channel')
            return (title, channel)
    except Exception:
        return (f'Video {video_id}', 'Unknown Channel')


def get_transcript_chunks(video_id: str) -> list[dict]:
    """
    Get transcript and split into overlapping sentence-aware chunks.

    Returns list of dicts with: text, start_seconds, end_seconds
    """
    return get_shared_transcript_chunks(video_id)


def detect_url_type(url: str) -> tuple[str, Optional[str]]:
    """
    Detect the type of YouTube URL and extract relevant ID.

    Returns:
        Tuple of (url_type, id) where url_type is 'channel', 'playlist', 'video', or 'unknown'
    """
    import re

    # Playlist URL patterns
    playlist_patterns = [
        r'[?&]list=([a-zA-Z0-9_-]+)',
        r'youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)',
    ]

    # Video URL patterns (check these BEFORE playlist since playlist URLs contain video IDs too)
    video_patterns = [
        r'[?&]v=([a-zA-Z0-9_-]{11})',  # Standard watch URL: ?v= or &v=
        r'youtu\.be/([a-zA-Z0-9_-]{11})',  # Short URL
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',  # Embed URL
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})',  # Old embed URL
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',  # Shorts URL
    ]

    # Channel URL patterns
    channel_patterns = [
        r'youtube\.com/@([a-zA-Z0-9_-]+)',
        r'youtube\.com/channel/([a-zA-Z0-9_-]+)',
        r'youtube\.com/c/([a-zA-Z0-9_-]+)',
        r'youtube\.com/user/([a-zA-Z0-9_-]+)',
    ]

    # Check for playlist first (since a video URL might also contain a playlist param)
    for pattern in playlist_patterns:
        match = re.search(pattern, url)
        if match:
            return ('playlist', match.group(1))

    # Check for video
    for pattern in video_patterns:
        match = re.search(pattern, url)
        if match:
            return ('video', match.group(1))

    # Check for channel
    for pattern in channel_patterns:
        match = re.search(pattern, url)
        if match:
            return ('channel', url)  # Return full URL for channel

    return ('unknown', None)


def ingest_single_video(video_id: str, api_key: str = None) -> Generator[str, None, None]:
    """
    Index a single YouTube video.

    Args:
        video_id: YouTube video ID

    Yields:
        Progress messages as strings
    """
    yield f"🎬 Processing single video: {video_id}"

    # Check if already indexed
    indexed_ids = get_indexed_video_ids(api_key)
    if video_id in indexed_ids:
        yield "✅ This video is already indexed!"
        return

    # Fetch video metadata using oEmbed API (more reliable for single videos)
    yield "📡 Fetching video info..."
    video_title, channel_name = fetch_video_metadata(video_id)
    yield f"📺 {video_title} by {channel_name}"

    # Get transcript chunks
    yield "📜 Fetching transcript..."
    chunks = get_transcript_chunks(video_id)

    if not chunks:
        yield "❌ Skipped: transcript unavailable, disabled, restricted, or still processing"
        return

    yield f"📊 Found {len(chunks)} transcript chunks"

    vectorstore = get_vectorstore(api_key)
    indexed_at = int(time.time())

    documents = []
    for chunk in chunks:
        doc = Document(
            page_content=chunk['text'],
            metadata={
                'video_id': video_id,
                'title': video_title,
                'channel_name': channel_name,
                'start_seconds': chunk['start_seconds'],
                'end_seconds': chunk['end_seconds'],
                'source_url': f"https://www.youtube.com/watch?v={video_id}",
                'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                'indexed_at': indexed_at
            }
        )
        documents.append(doc)

    try:
        vectorstore.add_documents(documents)
        yield f"✅ Indexed {len(chunks)} clips from video"
    except Exception as e:
        yield f"❌ Error indexing: {str(e)}"

    yield "🎉 Complete!"


def ingest_playlist(playlist_id: str, api_key: str = None) -> Generator[str, None, None]:
    """
    Index all videos from a YouTube playlist.

    Args:
        playlist_id: YouTube playlist ID

    Yields:
        Progress messages as strings
    """
    yield f"📋 Scanning playlist: {playlist_id}"

    try:
        videos = list(scrapetube.get_playlist(playlist_id))
    except Exception as e:
        yield f"❌ Error scanning playlist: {str(e)}"
        return

    total_videos = len(videos)
    yield f"📊 Found {total_videos} videos in playlist"

    # Get already indexed video IDs to skip
    indexed_ids = get_indexed_video_ids(api_key)
    yield f"📚 Database contains {len(indexed_ids)} previously indexed videos"

    # Filter to only new videos
    new_videos = [v for v in videos if v.get('videoId') not in indexed_ids]

    if not new_videos:
        yield "✅ All playlist videos already indexed!"
        return

    yield f"🆕 {len(new_videos)} new videos to index"

    vectorstore = get_vectorstore(api_key)
    indexed_count = 0
    skipped_count = 0

    for i, video in enumerate(new_videos, 1):
        video_id = video.get('videoId')
        title = extract_video_title(video)
        channel_name = extract_channel_name(video)

        yield f"📥 [{i}/{len(new_videos)}] Processing: {title[:50]}..."

        chunks = get_transcript_chunks(video_id)

        if not chunks:
            yield "   ⏭️ Skipped: transcript unavailable, disabled, restricted, or still processing"
            skipped_count += 1
            continue

        indexed_at = int(time.time())
        documents = []
        for chunk in chunks:
            doc = Document(
                page_content=chunk['text'],
                metadata={
                    'video_id': video_id,
                    'title': title,
                    'channel_name': channel_name,
                    'start_seconds': chunk['start_seconds'],
                    'end_seconds': chunk['end_seconds'],
                    'source_url': f"https://www.youtube.com/watch?v={video_id}",
                    'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                    'indexed_at': indexed_at
                }
            )
            documents.append(doc)

        try:
            vectorstore.add_documents(documents)
            indexed_count += 1
            yield f"   ✅ Indexed {len(chunks)} clips"
        except Exception as e:
            yield f"   ❌ Error indexing: {str(e)}"
            skipped_count += 1

        time.sleep(0.5)

    yield f"🎉 Complete! Indexed {indexed_count} videos ({skipped_count} skipped)"


def ingest_channel(channel_url: str, api_key: str = None) -> Generator[str, None, None]:
    """
    Index all videos from a YouTube channel.

    Yields progress messages for SSE streaming.
    Uses smart skip to avoid re-indexing existing videos.

    Args:
        channel_url: YouTube channel URL (e.g., https://www.youtube.com/@ChannelName)

    Yields:
        Progress messages as strings
    """
    yield "🔍 Scanning channel for videos..."

    try:
        # Get all videos from channel using scrapetube (no API key needed)
        # Use sort_by='oldest' to ensure full pagination through all videos
        # Increase sleep to 1.5s to avoid rate limiting on larger channels
        videos = list(scrapetube.get_channel(
            channel_url=channel_url,
            sort_by='oldest',
            sleep=1.5,
        ))
    except Exception as e:
        yield f"❌ Error scanning channel: {str(e)}"
        return

    total_videos = len(videos)
    yield f"📊 Found {total_videos} videos in channel"

    # Fetch channel name from first video using reliable oEmbed API
    # (scrapetube metadata is inconsistent and often returns "Unknown Channel")
    channel_name = "Unknown Channel"
    if videos:
        first_video_id = videos[0].get('videoId')
        if first_video_id:
            _, channel_name = fetch_video_metadata(first_video_id)
    yield f"📺 Channel: {channel_name}"

    # Get already indexed video IDs to skip
    indexed_ids = get_indexed_video_ids(api_key)
    yield f"📚 Database contains {len(indexed_ids)} previously indexed videos"

    # Filter to only new videos
    new_videos = [v for v in videos if v.get('videoId') not in indexed_ids]

    if not new_videos:
        yield "✅ All videos already indexed! Nothing new to process."
        return

    yield f"🆕 {len(new_videos)} new videos to index"

    # Get vectorstore for adding documents
    vectorstore = get_vectorstore(api_key)

    indexed_count = 0
    skipped_count = 0

    for i, video in enumerate(new_videos, 1):
        video_id = video.get('videoId')
        title = extract_video_title(video)
        # channel_name is already set above via oEmbed API (more reliable than scrapetube metadata)

        yield f"📥 [{i}/{len(new_videos)}] Processing: {title[:50]}..."

        # Get transcript chunks
        chunks = get_transcript_chunks(video_id)

        if not chunks:
            yield "   ⏭️ Skipped: transcript unavailable, disabled, restricted, or still processing"
            skipped_count += 1
            continue

        # Create LangChain documents from chunks
        indexed_at = int(time.time())
        documents = []
        for chunk in chunks:
            # Create document with rich metadata for search results
            doc = Document(
                page_content=chunk['text'],
                metadata={
                    'video_id': video_id,
                    'title': title,
                    'channel_name': channel_name,
                    'start_seconds': chunk['start_seconds'],
                    'end_seconds': chunk['end_seconds'],
                    'source_url': f"https://www.youtube.com/watch?v={video_id}",
                    'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                    'indexed_at': indexed_at
                }
            )
            documents.append(doc)

        # Add to vector store
        try:
            vectorstore.add_documents(documents)
            indexed_count += 1
            yield f"   ✅ Indexed {len(chunks)} clips"
        except Exception as e:
            yield f"   ❌ Error indexing: {str(e)}"
            skipped_count += 1

        # Brief pause to be a good citizen
        time.sleep(0.5)

    yield f"🎉 Complete! Indexed {indexed_count} videos ({skipped_count} skipped)"


def ingest_url(url: str, api_key: str = None) -> Generator[str, None, None]:
    """
    Smart ingestion that auto-detects URL type and handles appropriately.

    Supports:
    - Channel URLs (https://www.youtube.com/@ChannelName)
    - Playlist URLs (https://www.youtube.com/playlist?list=...)
    - Video URLs (https://www.youtube.com/watch?v=... or https://youtu.be/...)

    Args:
        url: Any YouTube URL

    Yields:
        Progress messages as strings
    """
    url_type, extracted_id = detect_url_type(url)

    yield f"🔗 Detected URL type: {url_type.upper()}"

    if url_type == 'channel':
        yield from ingest_channel(url, api_key)
    elif url_type == 'playlist':
        yield from ingest_playlist(extracted_id, api_key)
    elif url_type == 'video':
        yield from ingest_single_video(extracted_id, api_key)
    else:
        yield f"❌ Could not detect URL type. Please provide a valid YouTube channel, playlist, or video URL."
        yield "   Examples:"
        yield "   - Channel: https://www.youtube.com/@ChannelName"
        yield "   - Playlist: https://www.youtube.com/playlist?list=PLxxxxx"
        yield "   - Video: https://www.youtube.com/watch?v=xxxxx"


# For testing/standalone usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ingest.py <channel_url>")
        print("Example: python ingest.py https://www.youtube.com/@ThePrimeTimeagen")
        sys.exit(1)

    channel_url = sys.argv[1]
    print(f"\n🚀 Starting ingestion for: {channel_url}\n")

    for message in ingest_channel(channel_url):
        print(message)
