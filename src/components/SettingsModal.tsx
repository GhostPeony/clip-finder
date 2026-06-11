import React, { useState, useEffect } from 'react';
import {
  saveApiKey,
  deleteApiKey,
  fetchUsage,
  getStoredLocalApiKey,
  UsageInfo,
} from '../services/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  hasServerKey?: boolean;
  allowUserKeys?: boolean;
}

// Keep for backward compat during migration -- App.tsx still references this
export const getStoredApiKey = (): string | null => {
  return getStoredLocalApiKey();
};

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  allowUserKeys = true,
}) => {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [usage, setUsage] = useState<UsageInfo | null>(null);

  useEffect(() => {
    if (isOpen) {
      setApiKey('');
      setSaved(false);
      fetchUsage().then(setUsage);
    }
  }, [isOpen]);

  const handleSave = async () => {
    if (!apiKey.trim()) return;
    setSaving(true);
    const success = await saveApiKey(apiKey.trim());
    setSaving(false);
    if (success) {
      setSaved(true);
      fetchUsage().then(setUsage);
      setTimeout(() => onClose(), 1000);
    }
  };

  const handleClear = async () => {
    setSaving(true);
    await deleteApiKey();
    setSaving(false);
    setApiKey('');
    setSaved(true);
    fetchUsage().then(setUsage);
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(37,27,46,0.56)] px-4 backdrop-blur-sm"
      onClick={onClose}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        className="card w-full max-w-md p-6 shadow-lift"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="eyebrow mb-1">Workspace</p>
            <h2 className="font-serif text-3xl font-medium text-ink">Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 text-bark transition-colors hover:bg-cream hover:text-ink"
            title="Close settings"
            aria-label="Close settings"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Usage Quota */}
        {usage && (
          <div className="mb-5 rounded-xl bg-cream p-4">
            <h3 className="mb-3 font-serif text-2xl font-medium text-ink">Usage</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-bark">Searches this month</span>
                <span className="font-mono font-medium text-ink">
                  {usage.hasOwnKey
                    ? 'Own key'
                    : `${usage.searchesUsedThisMonth} / ${usage.searchLimit}`}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-bark">Videos indexed/accessed</span>
                <span className="font-mono font-medium text-ink">
                  {`${usage.indexedVideosUsed} / ${usage.indexedVideoLimit}`}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-bark">Transcript hours</span>
                <span className="font-mono font-medium text-ink">
                  {`${secondsToHours(usage.indexedSecondsUsed).toFixed(1)} / ${secondsToHours(
                    usage.indexedSecondsLimit ?? 0,
                  ).toFixed(1)}h`}
                </span>
              </div>
              {usage.searchLimit && (
                <div className="mt-2">
                  <div className="h-2 overflow-hidden rounded-full bg-petal">
                    <div
                      className="h-full rounded-full bg-teal transition-all"
                      style={{
                        width: `${Math.min(
                          100,
                          (usage.searchesUsedThisMonth / usage.searchLimit) * 100,
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              )}
              <p className="pt-2 text-xs leading-5 text-bark">
                Free imports process up to {usage.maxImportVideos} eligible videos at a time.
                Contact us when you are ready for a larger hosted library.
              </p>
            </div>
          </div>
        )}

        <div className="space-y-4">
          {allowUserKeys ? (
            <div>
              <label className="block text-sm font-semibold text-ink mb-1">
                Gemini API Key{' '}
                {usage?.hasOwnKey && <span className="font-normal text-leaf-deep">(active)</span>}
              </label>
              <p className="text-xs text-bark mb-2">
                Use your Gemini key for AI requests. Hosted indexing and storage caps still apply.
                Get one from{' '}
                <a
                  href="https://aistudio.google.com/app/apikey"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold text-violet-deep underline decoration-2 underline-offset-4"
                >
                  Google AI Studio
                </a>
              </p>
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => {
                    setApiKey(e.target.value);
                    setSaved(false);
                  }}
                  placeholder={usage?.hasOwnKey ? '(key stored securely)' : 'AIza...'}
                  className="input w-full px-3 py-2 pr-10 text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-ink"
                  aria-label={showKey ? 'Hide API key' : 'Show API key'}
                >
                  {showKey ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                      />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                      />
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                      />
                    </svg>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="rounded-xl bg-mint/40 p-4">
              <h3 className="mb-1 font-serif text-2xl font-medium text-ink">
                Model access included
              </h3>
              <p className="text-xs leading-5 text-bark">
                Embed Moments manages model access for this hosted workspace. You do not need to add
                or store an API key.
              </p>
            </div>
          )}

          <div className="rounded-xl bg-lavender/40 p-3 text-xs leading-5 text-ink">
            <strong>Security:</strong>{' '}
            {allowUserKeys
              ? 'Your key is encrypted on the server and used only for your Gemini API requests.'
              : 'Model credentials are never sent to the browser. Usage is protected by backend quotas.'}
          </div>
        </div>

        <div className="flex justify-between mt-6">
          {allowUserKeys ? (
            <button
              onClick={handleClear}
              disabled={saving}
              className="px-3 py-2 text-sm font-medium text-muted hover:text-rose-deep disabled:opacity-50"
            >
              Remove Key
            </button>
          ) : (
            <span className="px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted">
              Hosted access included
            </span>
          )}
          <div className="flex gap-2">
            <button onClick={onClose} className="btn btn-secondary min-h-0 px-4 py-2 text-sm">
              Cancel
            </button>
            {allowUserKeys && (
              <button
                onClick={handleSave}
                disabled={saving || !apiKey.trim()}
                className="btn btn-primary min-h-0 px-4 py-2 text-sm"
              >
                {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Key'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;

function secondsToHours(seconds: number): number {
  return seconds / 3600;
}
