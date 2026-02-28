import React, { useState, useEffect } from 'react';
import { saveApiKey, deleteApiKey, fetchUsage, UsageInfo } from '../services/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

// Keep for backward compat during migration -- App.tsx still references this
export const getStoredApiKey = (): string | null => {
  return null; // API key is now server-side
};

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-medium text-[#202124]">Settings</h2>
          <button onClick={onClose} className="text-[#5f6368] hover:text-[#202124] p-1">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Usage Quota */}
        {usage && (
          <div className="mb-5 p-4 bg-[#f8f9fa] rounded-lg border border-[#dadce0]">
            <h3 className="text-sm font-medium text-[#202124] mb-3">Usage</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-[#5f6368]">Searches today</span>
                <span className="text-[#202124] font-medium">
                  {usage.hasOwnKey ? 'Unlimited' : `${usage.searchesUsedToday} / ${usage.searchLimit}`}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-[#5f6368]">Videos indexed this month</span>
                <span className="text-[#202124] font-medium">
                  {usage.hasOwnKey ? 'Unlimited' : `${usage.indexesUsedThisMonth} / ${usage.indexLimit}`}
                </span>
              </div>
              {!usage.hasOwnKey && (
                <div className="mt-2">
                  <div className="h-1.5 bg-[#e8eaed] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#1a73e8] rounded-full transition-all"
                      style={{ width: `${Math.min(100, (usage.searchesUsedToday / usage.searchLimit) * 100)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#202124] mb-1">
              Gemini API Key {usage?.hasOwnKey && <span className="text-green-600 font-normal">(active)</span>}
            </label>
            <p className="text-xs text-[#5f6368] mb-2">
              Add your own key for unlimited usage. Get one from{' '}
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#1a73e8] hover:underline"
              >
                Google AI Studio
              </a>
            </p>
            <div className="relative">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => { setApiKey(e.target.value); setSaved(false); }}
                placeholder={usage?.hasOwnKey ? '(key stored securely)' : 'AIza...'}
                className="w-full px-3 py-2 border border-[#dadce0] rounded-md focus:outline-none focus:border-[#1a73e8] text-sm pr-10"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#5f6368] hover:text-[#202124]"
              >
                {showKey ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <div className="bg-[#e8f0fe] text-[#1967d2] text-xs p-3 rounded-md">
            <strong>Security:</strong> Your API key is encrypted and stored on the server.
            It's used only for your Gemini API requests and is never shared.
          </div>
        </div>

        <div className="flex justify-between mt-6">
          <button
            onClick={handleClear}
            disabled={saving}
            className="text-sm text-[#5f6368] hover:text-[#c5221f] px-3 py-2 disabled:opacity-50"
          >
            Remove Key
          </button>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="text-sm text-[#5f6368] hover:bg-[#f1f3f4] px-4 py-2 rounded-md"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !apiKey.trim()}
              className="text-sm bg-[#1a73e8] hover:bg-[#1557b0] text-white px-4 py-2 rounded-md font-medium disabled:opacity-50"
            >
              {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Key'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;
