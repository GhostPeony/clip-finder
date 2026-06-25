import { PRODUCT_NAME } from '../brand';

interface BrandLogoProps {
  showText?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClass = {
  sm: 'h-11 w-11',
  md: 'h-14 w-14',
  lg: 'h-20 w-20',
};

const LOGO_SRC = '/images/memexailogo-mark.png';

export function BrandMark({ className = '' }: { className?: string }) {
  return (
    <img
      src={LOGO_SRC}
      alt={`${PRODUCT_NAME} logo`}
      className={`object-contain ${className}`}
      width={64}
      height={64}
    />
  );
}

export function BrandLogo({ showText = true, size = 'md', className = '' }: BrandLogoProps) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <BrandMark className={`${sizeClass[size]} shrink-0`} />
      {showText ? (
        <span className="font-serif text-3xl font-medium leading-none text-ink">
          {PRODUCT_NAME}
        </span>
      ) : null}
    </div>
  );
}
