import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  formatDateTimeLabel,
  formatRelativeTime,
  formatTimestamp,
  formatTimestampLabel,
} from './time';

describe('formatRelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-01T12:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('uses a lowercase "just now" for fresh timestamps', () => {
    expect(formatRelativeTime(Date.now() - 30_000)).toBe('just now');
    expect(formatRelativeTime(new Date(Date.now() - 30_000).toISOString())).toBe('just now');
  });

  it('formats minutes, hours, and days', () => {
    expect(formatRelativeTime(Date.now() - 5 * 60_000)).toBe('5m ago');
    expect(formatRelativeTime(Date.now() - 3 * 3_600_000)).toBe('3h ago');
    expect(formatRelativeTime(Date.now() - 2 * 86_400_000)).toBe('2d ago');
  });

  it('falls back to a locale date beyond a week', () => {
    const old = Date.now() - 30 * 86_400_000;
    expect(formatRelativeTime(old)).toBe(new Date(old).toLocaleDateString());
  });

  it('returns unparseable strings unchanged', () => {
    expect(formatRelativeTime('not-a-date')).toBe('not-a-date');
  });
});

describe('formatTimestamp', () => {
  it('formats sub-hour timestamps as m:ss', () => {
    expect(formatTimestamp(0)).toBe('0:00');
    expect(formatTimestamp(65)).toBe('1:05');
    expect(formatTimestamp(59 * 60 + 59)).toBe('59:59');
  });

  it('is hour-aware above one hour', () => {
    expect(formatTimestamp(3665)).toBe('1:01:05');
    expect(formatTimestamp(2 * 3600)).toBe('2:00:00');
  });

  it('clamps negative and fractional input', () => {
    expect(formatTimestamp(-5)).toBe('0:00');
    expect(formatTimestamp(65.9)).toBe('1:05');
  });
});

describe('formatTimestampLabel', () => {
  it('labels the zero timestamp as the start of the video', () => {
    expect(formatTimestampLabel(0)).toBe('Start of video');
  });

  it('matches formatTimestamp for non-zero values', () => {
    expect(formatTimestampLabel(302)).toBe('5:02');
    expect(formatTimestampLabel(3665)).toBe('1:01:05');
  });
});

describe('formatDateTimeLabel', () => {
  it('returns empty for missing or invalid values', () => {
    expect(formatDateTimeLabel()).toBe('');
    expect(formatDateTimeLabel(null)).toBe('');
    expect(formatDateTimeLabel('not-a-date')).toBe('');
  });

  it('formats a locale month/day time label', () => {
    const value = '2026-06-24T06:30:55Z';
    const expected = new Intl.DateTimeFormat(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }).format(new Date(value));
    expect(formatDateTimeLabel(value)).toBe(expected);
  });
});
