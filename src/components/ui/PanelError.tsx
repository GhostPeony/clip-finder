import React from 'react';

/**
 * Honest per-panel failure state: a short human label plus a Retry action.
 * Rendered inside a panel body when its data fetch failed.
 */
export function PanelError({ label, onRetry }: { label: string; onRetry: () => void }) {
  return (
    <div role="alert" className="rounded-xl bg-cream p-3">
      <p className="text-sm leading-6 text-bark">{label}</p>
      <button type="button" onClick={onRetry} className="link-quiet mt-2 text-sm">
        Retry
      </button>
    </div>
  );
}
