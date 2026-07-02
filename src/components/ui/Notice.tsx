import React from 'react';
import { cn } from '../../lib/cn';

export type NoticeTone = 'success' | 'error' | 'info';

export interface NoticeState {
  message: string;
  tone: NoticeTone;
}

const TONE_CLASS: Record<NoticeTone, string> = {
  success: 'bg-mint/40 text-leaf-deep',
  error: 'bg-rose/10 text-rose-deep',
  info: 'bg-lavender/40 text-violet-deep',
};

/**
 * Inline status pill for action feedback. Errors announce as alerts;
 * success/info announce politely as status.
 */
export function Notice({
  tone = 'info',
  role,
  className = '',
  children,
}: {
  tone?: NoticeTone;
  role?: 'alert' | 'status';
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <p
      role={role ?? (tone === 'error' ? 'alert' : 'status')}
      className={cn('rounded-lg px-3 py-2 text-xs font-medium', TONE_CLASS[tone], className)}
    >
      {children}
    </p>
  );
}
