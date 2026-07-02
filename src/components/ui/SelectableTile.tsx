import React from 'react';
import { cn } from '../../lib/cn';

export type SelectableTileVariant = 'flat' | 'bordered';

const SELECTED_CLASS: Record<SelectableTileVariant, string> = {
  flat: 'bg-surface text-ink shadow-soft',
  bordered: 'border-rose/30 bg-surface text-ink shadow-soft',
};

const UNSELECTED_CLASS: Record<SelectableTileVariant, string> = {
  flat: 'bg-cream text-bark hover:bg-petal/50 hover:text-ink',
  bordered: 'border-ink/10 bg-cream text-bark hover:text-ink',
};

interface SelectableTileProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  selected: boolean;
  variant?: SelectableTileVariant;
  /** Override the resting (unselected) classes when the tile sits on a non-cream surface. */
  unselectedClassName?: string;
}

/**
 * Selection tile button with the single shared selected style
 * (`bg-surface text-ink shadow-soft`). Layout classes come from the call site.
 */
export function SelectableTile({
  selected,
  variant = 'flat',
  unselectedClassName,
  className = '',
  children,
  ...rest
}: SelectableTileProps) {
  return (
    <button
      type="button"
      className={cn(
        className,
        selected ? SELECTED_CLASS[variant] : (unselectedClassName ?? UNSELECTED_CLASS[variant]),
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
