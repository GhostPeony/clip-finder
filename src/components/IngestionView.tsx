import React, { useState, useEffect, useRef } from 'react';
import { ingestChannel } from '../services/api';

interface IngestionViewProps {
  onComplete: () => void;
  isBackendConnected: boolean;
}

export const IngestionView: React.FC<IngestionViewProps> = ({ onComplete, isBackendConnected }) => {
  const [url, setUrl] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const handleStartIngestion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    if (!isBackendConnected) {
      setLogs(["Error: Backend not connected. Cannot start ingestion."]);
      return;
    }

    setIsIngesting(true);
    setLogs([]);

    await ingestChannel(
      url,
      (msg) => setLogs(prev => [...prev, msg]),
      () => {
        setLogs(prev => {
          const allLogs = prev.join(' ');
          const hasError = allLogs.includes('❌') || allLogs.includes('No transcript') || allLogs.includes('Error');
          const hasSuccess = allLogs.includes('✅ Indexed') || allLogs.includes('🎉 Complete');

          if (hasError && !hasSuccess) {
            setIsIngesting(false);
            return [...prev, "⚠️ Ingestion had issues. Review and try a different URL."];
          } else if (hasSuccess) {
            onComplete();  // Switch to search immediately
            return [...prev, "✅ Success! Switching to search..."];
          } else {
            setIsIngesting(false);
            return [...prev, "Ingestion finished."];
          }
        });
      }
    );
  };

  return (
    <div className="max-w-xl mx-auto w-full">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="flex justify-center mb-4">
          <svg className="w-16 h-16" viewBox="0 0 48 48" fill="none">
            <circle cx="22" cy="22" r="14" stroke="#ea4335" strokeWidth="4" />
            <path d="M32 32l12 12" stroke="#4285f4" strokeWidth="4" strokeLinecap="round" />
            <path d="M18 22h8M22 18v8" stroke="#34a853" strokeWidth="3" strokeLinecap="round" />
          </svg>
        </div>
        <h1 className="text-2xl font-normal text-[#202124] mb-2">
          Index YouTube Content
        </h1>
        <p className="text-[#5f6368] text-sm">
          Enter a channel, playlist, or video URL to make it searchable with AI
        </p>
      </div>

      {/* Main Card */}
      <div className="bg-white rounded-lg border border-[#dadce0] shadow-sm">
        {!isIngesting ? (
          <form onSubmit={handleStartIngestion} className="p-6">
            <label htmlFor="url" className="block text-sm font-medium text-[#202124] mb-2">
              YouTube URL
            </label>
            <div className="flex gap-3">
              <input
                id="url"
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Channel, playlist, or video URL"
                disabled={!isBackendConnected}
                className="flex-1 px-4 py-2 border border-[#dadce0] rounded-md focus:outline-none focus:border-[#1a73e8] focus:ring-1 focus:ring-[#1a73e8] text-sm disabled:bg-[#f1f3f4] disabled:cursor-not-allowed"
              />
              <button
                type="submit"
                disabled={!isBackendConnected || !url.trim()}
                className="bg-[#1a73e8] hover:bg-[#1557b0] text-white px-6 py-2 rounded-md text-sm font-medium disabled:bg-[#dadce0] disabled:cursor-not-allowed transition-colors"
              >
                Index
              </button>
            </div>

            {!isBackendConnected && (
              <div className="mt-4 bg-[#fce8e6] border border-[#f5c6cb] rounded-lg p-4">
                <div className="flex gap-3">
                  <svg className="w-5 h-5 text-[#c5221f] flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <div className="text-sm text-[#c5221f]">
                    <p className="font-medium">Backend Unavailable</p>
                    <p className="mt-1 text-[#5f6368]">Run the Python server:</p>
                    <code className="block bg-[#f1f3f4] text-[#202124] p-2 mt-2 rounded text-xs">
                      pip install -r requirements.txt && python server.py
                    </code>
                  </div>
                </div>
              </div>
            )}

            {/* How It Works + Formats */}
            <div className="mt-6 pt-6 border-t border-[#dadce0]">
              <h3 className="text-xs font-medium text-[#5f6368] uppercase tracking-wide mb-4">How It Works</h3>

              <div className="space-y-3 mb-5">
                <div className="flex gap-3 items-start">
                  <div className="w-6 h-6 rounded-full bg-[#e8f0fe] text-[#1a73e8] flex items-center justify-center text-xs font-medium flex-shrink-0">1</div>
                  <div>
                    <p className="text-sm text-[#202124] font-medium">Index your videos</p>
                    <p className="text-xs text-[#5f6368]">Paste a channel, playlist, or video URL above. We automatically extract and process all transcripts.</p>
                  </div>
                </div>
                <div className="flex gap-3 items-start">
                  <div className="w-6 h-6 rounded-full bg-[#e8f0fe] text-[#1a73e8] flex items-center justify-center text-xs font-medium flex-shrink-0">2</div>
                  <div>
                    <p className="text-sm text-[#202124] font-medium">Ask any question</p>
                    <p className="text-xs text-[#5f6368]">Search in plain language. We use RAG (Retrieval-Augmented Generation) with Gemini to find the most relevant clips.</p>
                  </div>
                </div>
                <div className="flex gap-3 items-start">
                  <div className="w-6 h-6 rounded-full bg-[#e8f0fe] text-[#1a73e8] flex items-center justify-center text-xs font-medium flex-shrink-0">3</div>
                  <div>
                    <p className="text-sm text-[#202124] font-medium">Find the exact moment</p>
                    <p className="text-xs text-[#5f6368]">Click any citation to jump directly to that timestamp. No more scrubbing through hours of content!</p>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 text-xs text-[#5f6368] justify-center">
                <span className="bg-[#f1f3f4] px-2 py-1 rounded">📺 Channels</span>
                <span className="bg-[#f1f3f4] px-2 py-1 rounded">📋 Playlists</span>
                <span className="bg-[#f1f3f4] px-2 py-1 rounded">🎬 Videos</span>
              </div>

              <div className="mt-4 text-xs text-[#5f6368] text-center space-x-4">
                <span>✓ API key needed for index & search</span>
                <span>✓ Data stored locally</span>
              </div>
            </div>
          </form>
        ) : (
          <div className="p-6">
            {/* Centered Spinner with Status */}
            <div className="flex flex-col items-center justify-center py-12">
              {/* Spinning Circle */}
              <div className="relative">
                <div className="w-16 h-16 border-4 border-[#e8f0fe] rounded-full"></div>
                <div className="absolute top-0 left-0 w-16 h-16 border-4 border-transparent border-t-[#1a73e8] rounded-full animate-spin"></div>
              </div>

              {/* Current Status - Single Line */}
              <p className="mt-6 text-sm text-[#3c4043] text-center min-h-[1.5rem] transition-all">
                {logs.length > 0 ? logs[logs.length - 1] : 'Starting...'}
              </p>

              {/* Subtle message count */}
              <p className="mt-2 text-xs text-[#9aa0a6]">
                {logs.length > 0 && `Step ${logs.length}`}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Footer Note */}
      <p className="text-center text-xs text-[#5f6368] mt-6">
        Powered by Ghost Peony
      </p>
    </div>
  );
};

export default IngestionView;
