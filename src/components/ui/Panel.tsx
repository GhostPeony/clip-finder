import React from 'react';
import { cn } from '../../lib/cn';

export type PanelSize = 'compact' | 'section';

const TITLE_CLASS: Record<PanelSize, string> = {
  compact: 'font-serif text-xl font-medium text-ink',
  section: 'font-serif text-2xl font-medium text-ink',
};

const DESCRIPTION_CLASS: Record<PanelSize, string> = {
  compact: 'mt-1 text-xs font-medium text-muted',
  section: 'mt-1 max-w-2xl text-sm leading-6 text-bark',
};

/**
 * Shared card panel with a title/description header and an optional action slot.
 * `compact` is the dashboard-widget scale; `section` is the library section scale.
 */
export function Panel({
  title,
  description,
  action,
  size = 'compact',
  className = '',
  children,
}: {
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  size?: PanelSize;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={cn('card min-w-0 overflow-hidden p-4 sm:p-5', className)}>
      <div className="mb-3 flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className={TITLE_CLASS[size]}>{title}</h2>
          {description ? <p className={DESCRIPTION_CLASS[size]}>{description}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}
