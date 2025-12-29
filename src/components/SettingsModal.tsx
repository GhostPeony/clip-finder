import React, { useState, useEffect } from 'react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const API_KEY_STORAGE_KEY = 'clipfinder_api_key';

export const getStoredApiKey = (): string | null => {
  return localStorage.getItem(API_KEY_STORAGE_KEY);
};

export const setStoredApiKey = (key: string | null): void => {
  if (key) {
    localStorage.setItem(API_KEY_STORAGE_KEY, key);
  } else {
    localStorage.removeItem(API_KEY_STORAGE_KEY);
  }
};

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const stored = getStoredApiKey();
      setApiKey(stored || '');
      setSaved(false);
    }
  }, [isOpen]);

  const handleSave = () => {
    setStoredApiKey(apiKey.trim() || null);
    setSaved(true);
    setTimeout(() => onClose(), 1000);
  };

  const handleClear = () => {
    setApiKey('');
    setStoredApiKey(null);
    setSaved(true);
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

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#202124] mb-1">
              Gemini API Key
            </label>
            <p className="text-xs text-[#5f6368] mb-2">
              Get your free API key from{' '}
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
                placeholder="AIza..."
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
            <strong>Privacy:</strong> Your API key is stored locally in your browser and never sent to our servers.
            It's only used to make requests directly to Google's Gemini API.
          </div>
        </div>

        <div className="flex justify-between mt-6">
          <button
            onClick={handleClear}
            className="text-sm text-[#5f6368] hover:text-[#c5221f] px-3 py-2"
          >
            Clear Key
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
              className="text-sm bg-[#1a73e8] hover:bg-[#1557b0] text-white px-4 py-2 rounded-md font-medium"
            >
              {saved ? '✓ Saved!' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;
