/** Shared time/date formatting for clips, jobs, and history entries. */

/**
 * Relative "ago" label for a timestamp (ISO string or epoch milliseconds).
 * Returns the raw string back when it cannot be parsed.
 */
export function formatRelativeTime(value: string | number): string {
  const timestamp = typeof value === 'number' ? value : new Date(value).getTime();
  if (Number.isNaN(timestamp)) return String(value);
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString();
}

/** Compact clip timestamp: `4:05`, and hour-aware above one hour: `1:01:05`. */
export function formatTimestamp(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds || 0));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const remainingSeconds = safeSeconds % 60;
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${remainingSeconds
      .toString()
      .padStart(2, '0')}`;
  }
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

/** Human timestamp label for source links: `Start of video`, `4:05`, `1:01:05`. */
export function formatTimestampLabel(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds || 0));
  if (safeSeconds === 0) return 'Start of video';
  return formatTimestamp(safeSeconds);
}

/** Locale date-time label like `Jun 24, 6:30 AM`. Empty string for missing values. */
export function formatDateTimeLabel(value?: string | null): string {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(parsed);
}
