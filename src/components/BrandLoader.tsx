import { BrandMark } from './BrandLogo';

interface BrandLoaderProps {
  label?: string;
  detail?: string;
  compact?: boolean;
  className?: string;
}

export function BrandLoader({
  label = 'Loading...',
  detail,
  compact = false,
  className = '',
}: BrandLoaderProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center ${compact ? 'py-4' : 'py-10'} ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className="brand-loader-mark">
        <BrandMark className={compact ? 'h-10 w-10' : 'h-14 w-14'} />
      </div>
      <p className={`${compact ? 'mt-3' : 'mt-4'} text-sm font-semibold text-ink`}>{label}</p>
      {detail ? <p className="mt-1 max-w-xs text-xs leading-5 text-bark">{detail}</p> : null}
    </div>
  );
}
