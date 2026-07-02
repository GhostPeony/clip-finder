import React, { useEffect, useState } from 'react';
import { VideoClip } from '../../types';
import { saveSearchToHistory, searchVideoClips } from '../../services/api';
import { LibrarySearchMode, LibrarySearchPanel } from './LibrarySearchPanel';

const LIBRARY_SEARCH_RESULT_LIMIT = 5;

/**
 * Owns library-search state (query, mode, results) so the search panel can
 * render at the top of the Library page, independent of the browse panels.
 */
export function LibrarySearchSection({
  projectId,
  projectName,
}: {
  projectId?: string | null;
  projectName?: string;
}) {
  const [mode, setMode] = useState<LibrarySearchMode>('auto');
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [answer, setAnswer] = useState('');
  const [results, setResults] = useState<VideoClip[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    setAnswer('');
    setResults([]);
    setError('');
  }, [projectId]);

  const handleSearch = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;

    setSearching(true);
    setError('');
    setAnswer('');
    setResults([]);
    try {
      const { answer: nextAnswer, relevantClips } = projectId
        ? await searchVideoClips(
            trimmedQuery,
            LIBRARY_SEARCH_RESULT_LIMIT,
            undefined,
            mode,
            projectId,
          )
        : await searchVideoClips(trimmedQuery, LIBRARY_SEARCH_RESULT_LIMIT, undefined, mode);
      const clips = relevantClips.filter((clip) => clip.videoId);
      setAnswer(nextAnswer || '');
      setResults(clips);
      if (clips.length > 0) {
        saveSearchToHistory(trimmedQuery, clips);
      }
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  return (
    <LibrarySearchPanel
      mode={mode}
      query={query}
      searching={searching}
      answer={answer}
      results={results}
      error={error}
      onModeChange={setMode}
      onQueryChange={setQuery}
      onSubmit={(event) => void handleSearch(event)}
      projectName={projectName}
    />
  );
}
