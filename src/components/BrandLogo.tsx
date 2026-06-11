import { PRODUCT_NAME } from '../brand';

interface BrandLogoProps {
  showText?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClass = {
  sm: 'h-9 w-9',
  md: 'h-12 w-12',
  lg: 'h-16 w-16',
};

/**
 * Logomark: a timeline with the exact moment marked.
 * Keep in sync with public/favicon.svg.
 */
export function BrandMark({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} role="img" aria-label={`${PRODUCT_NAME} logo`}>
      <rect width="48" height="48" rx="14" fill="var(--peony-ink)" />
      <line
        x1="10"
        y1="24"
        x2="38"
        y2="24"
        stroke="var(--peony-cream)"
        strokeOpacity="0.35"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <line
        x1="10"
        y1="24"
        x2="29"
        y2="24"
        stroke="var(--peony-cream)"
        strokeOpacity="0.85"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <circle cx="29" cy="24" r="8" fill="var(--peony-rose)" fillOpacity="0.28" />
      <circle cx="29" cy="24" r="4.5" fill="var(--peony-rose)" />
    </svg>
  );
}

export function BrandLogo({ showText = true, size = 'md', className = '' }: BrandLogoProps) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <BrandMark className={`${sizeClass[size]} shrink-0`} />
      {showText ? (
        <span className="font-serif text-2xl font-medium leading-none text-ink">
          {PRODUCT_NAME}
        </span>
      ) : null}
    </div>
  );
}
