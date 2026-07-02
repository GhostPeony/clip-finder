import { useEffect, useRef } from 'react';

interface UsePollingOptions {
  /** Pause the interval (and visibility refresh) entirely when false. */
  enabled?: boolean;
  /** Runs when the tab becomes visible again; defaults to the interval callback. */
  onVisibilityRefresh?: () => void | Promise<void>;
}

/**
 * Interval polling that only fires while the document is visible.
 * Returning to a visible tab triggers an immediate refresh instead of
 * waiting for the next tick.
 */
export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs: number,
  { enabled = true, onVisibilityRefresh }: UsePollingOptions = {},
): void {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;
  const visibilityRefreshRef = useRef(onVisibilityRefresh);
  visibilityRefreshRef.current = onVisibilityRefresh;

  useEffect(() => {
    if (!enabled) return;

    const tick = () => {
      if (document.visibilityState !== 'visible') return;
      void callbackRef.current();
    };

    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible') return;
      const refresh = visibilityRefreshRef.current ?? callbackRef.current;
      void refresh();
    };

    const interval = window.setInterval(tick, intervalMs);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [enabled, intervalMs]);
}
