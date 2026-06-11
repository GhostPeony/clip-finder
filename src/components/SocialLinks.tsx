import {
  CADE_LINKEDIN_URL,
  CONTACT_EMAIL,
  GHOST_PEONY_GITHUB_URL,
  GHOST_PEONY_SUBSTACK_URL,
  GHOST_PEONY_URL,
} from '../brand';

type SocialKind = 'github' | 'website' | 'substack' | 'linkedin' | 'email';

interface SocialLinkItem {
  href: string;
  label: string;
  kind: SocialKind;
}

const socialLinks: SocialLinkItem[] = [
  { href: GHOST_PEONY_URL, label: 'Ghost Peony', kind: 'website' },
  { href: GHOST_PEONY_GITHUB_URL, label: 'GitHub', kind: 'github' },
  { href: GHOST_PEONY_SUBSTACK_URL, label: 'Substack', kind: 'substack' },
  { href: CADE_LINKEDIN_URL, label: 'LinkedIn', kind: 'linkedin' },
  { href: `mailto:${CONTACT_EMAIL}`, label: CONTACT_EMAIL, kind: 'email' },
];

interface SocialLinksProps {
  className?: string;
  compact?: boolean;
  tone?: 'light' | 'dark';
}

export function SocialLinks({ className = '', compact = false, tone = 'dark' }: SocialLinksProps) {
  return (
    <nav
      aria-label="Ghost Peony links"
      className={`flex flex-wrap items-center gap-2 ${className}`}
    >
      {socialLinks.map((link) => (
        <SocialIconLink key={link.href} link={link} compact={compact} tone={tone} />
      ))}
    </nav>
  );
}

function SocialIconLink({
  link,
  compact,
  tone,
}: {
  link: SocialLinkItem;
  compact: boolean;
  tone: 'light' | 'dark';
}) {
  const external = !link.href.startsWith('mailto:');
  const colorClass =
    tone === 'light'
      ? 'border-cream/25 text-cream/80 hover:border-cream/50 hover:text-cream'
      : 'border-ink/15 text-bark hover:border-ink/30 hover:text-ink';

  return (
    <a
      href={link.href}
      target={external ? '_blank' : undefined}
      rel={external ? 'noopener noreferrer' : undefined}
      className={`inline-flex min-h-10 items-center gap-2 rounded-full border px-4 py-2 text-xs font-medium transition-colors ${colorClass}`}
      title={link.label}
    >
      <SocialIcon kind={link.kind} />
      {compact ? <span className="sr-only">{link.label}</span> : <span>{link.label}</span>}
    </a>
  );
}

function SocialIcon({ kind }: { kind: SocialKind }) {
  if (kind === 'github') {
    return (
      <svg aria-hidden="true" className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 .297C5.37.297 0 5.67 0 12.297c0 5.304 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.011-1.23-.017-2.23-3.338.725-4.043-1.415-4.043-1.415-.546-1.387-1.333-1.757-1.333-1.757-1.09-.745.082-.73.082-.73 1.205.085 1.84 1.237 1.84 1.237 1.07 1.835 2.809 1.305 3.495.998.108-.775.418-1.305.762-1.605-2.665-.303-5.466-1.332-5.466-5.93 0-1.31.468-2.382 1.235-3.222-.124-.303-.535-1.523.117-3.176 0 0 1.008-.322 3.3 1.23a11.48 11.48 0 0 1 3.003-.404c1.019.005 2.045.138 3.003.404 2.29-1.552 3.296-1.23 3.296-1.23.654 1.653.243 2.873.12 3.176.77.84 1.233 1.912 1.233 3.222 0 4.61-2.806 5.624-5.478 5.921.43.371.823 1.102.823 2.222 0 1.606-.015 2.898-.015 3.293 0 .321.216.695.825.577C20.565 22.093 24 17.599 24 12.297c0-6.627-5.373-12-12-12" />
      </svg>
    );
  }

  if (kind === 'linkedin') {
    return (
      <svg aria-hidden="true" className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
        <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
      </svg>
    );
  }

  if (kind === 'substack') {
    return (
      <svg aria-hidden="true" className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
        <path d="M3 2.75h18v2.5H3v-2.5Zm0 4.5h18v2.5H3v-2.5Zm0 4.5h18v9.5l-9-5.05-9 5.05v-9.5Z" />
      </svg>
    );
  }

  if (kind === 'email') {
    return (
      <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24">
        <path
          d="M4 6.5h16v11H4v-11Zm1.2 1.1L12 12.2l6.8-4.6"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24">
      <path
        d="M12 21a9 9 0 1 0 0-18m0 18a9 9 0 1 1 0-18m0 18c2 0 3.5-4 3.5-9S14 3 12 3m0 18c-2 0-3.5-4-3.5-9S10 3 12 3M3.5 12h17"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
    </svg>
  );
}
