import type { CSSProperties } from 'react';
import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { GHOST_PEONY_NAME, GHOST_PEONY_URL, PRODUCT_DOMAIN, PRODUCT_NAME } from '../brand';
import { BrandLogo } from './BrandLogo';
import { SocialLinks } from './SocialLinks';

const workflowSteps = [
  [
    '01',
    'Pull the transcript',
    'Paste a video, playlist, or channel. Embed Moments turns captions into timestamped transcript segments.',
  ],
  [
    '02',
    'Embed the memory',
    'Every segment is embedded for retrieval, so you search by meaning instead of guessing keywords.',
  ],
  [
    '03',
    'Land on the proof',
    'Answers point back to clips and timestamps you can verify before you quote, clip, or cite.',
  ],
];

const useCases = [
  [
    'Ask instead of watching',
    'No time for a 90-minute video? Drop it in and ask questions. Get a sourced answer with exact timestamps — no scrubbing.',
  ],
  ['Embed a quote', 'Find the exact timestamp for an article, launch page, newsletter, or lesson.'],
  ['Clip a short', 'Turn long interviews and commentary into source-backed short-form candidates.'],
  ['Recover a claim', 'Search for the story, objection, demo, or answer you half-remember.'],
  [
    'Build a memory bank',
    'Keep channels, talks, demos, and references searchable as a private library.',
  ],
];

function MomentVignette() {
  return (
    <div className="card p-6 sm:p-8" aria-hidden="true">
      <p className="eyebrow">Answer with receipts</p>
      <p className="mt-4 font-serif text-xl text-ink sm:text-2xl">
        &ldquo;Where did she explain why the pricing changed?&rdquo;
      </p>
      <div className="mt-5 rounded-xl bg-cream p-4 sm:p-5">
        <p className="text-sm leading-6 text-bark">
          The pricing change comes up twice. The full reasoning — moving from seats to usage so
          small teams aren&rsquo;t penalized — is laid out in the Q2 roadmap review.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <span className="chip">
            <svg className="h-3 w-3" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
            Roadmap review <span className="font-mono">14:32</span>
          </span>
          <span className="chip chip-violet">
            <svg className="h-3 w-3" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
            Community Q&amp;A <span className="font-mono">41:07</span>
          </span>
        </div>
      </div>
      <p className="mt-4 text-xs text-muted">
        Click a citation, land on the exact second it happens.
      </p>
    </div>
  );
}

export function LandingPage() {
  const { signInWithGoogle } = useAuth();
  const [googleLoading, setGoogleLoading] = useState(false);
  const [authError, setAuthError] = useState('');

  useEffect(() => {
    const elements = Array.from(document.querySelectorAll<HTMLElement>('.scroll-reveal'));

    if (!('IntersectionObserver' in window)) {
      elements.forEach((element) => element.classList.add('is-visible'));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        });
      },
      {
        rootMargin: '0px 0px -10% 0px',
        threshold: 0.18,
      },
    );

    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  const handleGoogleSignIn = async () => {
    setGoogleLoading(true);
    setAuthError('');
    const { error } = await signInWithGoogle();
    if (error) {
      setAuthError(error.message);
      setGoogleLoading(false);
    }
  };

  return (
    <div className="landing-page min-h-screen overflow-hidden bg-cream text-ink">
      <header className="landing-reveal fixed top-0 z-50 w-full border-b border-ink/10 bg-cream/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <BrandLogo size="sm" />
          <nav className="hidden items-center gap-8 text-sm font-medium text-bark md:flex">
            <a href="#workflow" className="transition-colors hover:text-ink">
              Workflow
            </a>
            <a href="#use-cases" className="transition-colors hover:text-ink">
              Use cases
            </a>
          </nav>
          <button
            onClick={handleGoogleSignIn}
            disabled={googleLoading}
            className="btn btn-primary min-h-10 whitespace-nowrap px-4 py-2 text-sm sm:px-6"
          >
            {googleLoading ? 'Redirecting...' : 'Login'}
          </button>
        </div>
      </header>

      <main className="pt-16">
        <section className="glow-wash relative">
          <div className="mx-auto max-w-6xl px-5 pb-24 pt-20 sm:pt-28 md:pb-32 md:pt-36">
            <div className="max-w-4xl">
              <h1
                className="landing-reveal font-serif text-5xl font-medium leading-[1.02] tracking-tight sm:text-7xl md:text-8xl"
                style={{ '--reveal-delay': '0.1s' } as CSSProperties}
              >
                A searchable <em className="italic text-rose-deep">memory</em> for everything you
                watch.
              </h1>
              <p
                className="landing-reveal mt-8 max-w-2xl text-lg leading-8 text-bark md:text-xl"
                style={{ '--reveal-delay': '0.3s' } as CSSProperties}
              >
                You half-remember a quote, a claim, a moment. Index any YouTube channel, playlist,
                or video — then ask, and land on the exact second it happens.
              </p>
              <div
                className="landing-reveal mt-10 flex flex-col items-start gap-5 sm:flex-row sm:items-center"
                style={{ '--reveal-delay': '0.5s' } as CSSProperties}
              >
                <button
                  onClick={handleGoogleSignIn}
                  disabled={googleLoading}
                  className="btn btn-primary px-8 py-3 text-base"
                >
                  {googleLoading ? 'Redirecting...' : 'Start free'}
                </button>
                <a href="#workflow" className="link-quiet text-sm">
                  See how it works
                </a>
              </div>
              {authError && (
                <p
                  className="landing-reveal mt-5 max-w-md text-sm font-medium text-rose-deep"
                  role="status"
                  style={{ '--reveal-delay': '0.6s' } as CSSProperties}
                >
                  {authError}
                </p>
              )}
            </div>
          </div>
        </section>

        <section id="workflow" className="scroll-reveal">
          <div className="mx-auto max-w-6xl px-5 py-20 md:py-28">
            <div className="mb-14 grid gap-6 md:grid-cols-[1.1fr_0.9fr] md:items-end">
              <h2 className="font-serif text-4xl font-medium tracking-tight md:text-6xl">
                Search video like memory, not metadata.
              </h2>
              <p className="max-w-xl text-base leading-7 text-bark">
                You don&rsquo;t need the title, the channel, or the timestamp. Describe the moment
                you&rsquo;re after and land on the exact second it happens.
              </p>
            </div>
            <div className="grid gap-6 md:grid-cols-3">
              {workflowSteps.map(([number, title, body], index) => (
                <article
                  key={title}
                  className="scroll-reveal card card-lift p-7"
                  style={{ '--scroll-delay': `${index * 0.1}s` } as CSSProperties}
                >
                  <p className="font-serif text-2xl text-rose-deep">{number}</p>
                  <h3 className="mt-4 font-serif text-2xl font-medium md:text-3xl">{title}</h3>
                  <p className="mt-3 text-sm leading-6 text-bark">{body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="proof" className="scroll-reveal">
          <div className="mx-auto grid max-w-6xl gap-12 px-5 py-20 md:grid-cols-[0.85fr_1.15fr] md:items-center md:py-28">
            <div>
              <h2 className="font-serif text-4xl font-medium tracking-tight md:text-6xl">
                Long videos, exact moments.
              </h2>
              <p className="mt-6 max-w-md text-base leading-7 text-bark">
                Ask a question across everything you&rsquo;ve indexed. Every answer cites the clips
                it came from, so you verify before you publish — no scrubbing, no guessing.
              </p>
            </div>
            <div className="scroll-reveal" style={{ '--scroll-delay': '0.15s' } as CSSProperties}>
              <MomentVignette />
            </div>
          </div>
        </section>

        <section id="use-cases" className="scroll-reveal bg-petal/40">
          <div className="mx-auto max-w-6xl px-5 py-20 md:py-28">
            <div className="grid gap-10 md:grid-cols-[0.85fr_1.15fr] md:items-start">
              <h2 className="font-serif text-4xl font-medium tracking-tight md:text-6xl">
                Put everything you&rsquo;ve watched to work.
              </h2>
              <div className="grid gap-5 sm:grid-cols-2">
                {useCases.map(([title, body], index) => (
                  <article
                    key={title}
                    className={`scroll-reveal card card-lift p-6 ${index === 0 ? 'sm:col-span-2' : ''}`}
                    style={{ '--scroll-delay': `${index * 0.08}s` } as CSSProperties}
                  >
                    <h3 className="font-serif text-2xl font-medium">{title}</h3>
                    <p className="mt-2 text-sm leading-6 text-bark">{body}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="scroll-reveal glow-wash">
          <div className="mx-auto max-w-6xl px-5 py-24 text-center md:py-32">
            <h2 className="font-serif text-4xl font-medium tracking-tight md:text-7xl">
              Stop scrubbing. Start asking.
            </h2>
            <p className="mx-auto mt-6 max-w-xl text-base leading-7 text-bark md:text-lg">
              Free to start — index a channel and find your first moment in minutes.
            </p>
            <div className="mt-10 flex justify-center">
              <button
                onClick={handleGoogleSignIn}
                disabled={googleLoading}
                className="btn btn-primary px-8 py-3 text-base"
              >
                {googleLoading ? 'Redirecting...' : 'Start free'}
              </button>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-ink px-5 py-12 text-cream">
        <div className="mx-auto flex max-w-6xl flex-col justify-between gap-8 text-sm lg:flex-row lg:items-end">
          <div>
            <span className="font-serif text-3xl">{PRODUCT_NAME}</span>
            <p className="mt-3 max-w-xl leading-6 text-cream/75">
              A searchable memory for everything you watch. Built by{' '}
              <a
                href={GHOST_PEONY_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="font-semibold text-cream underline decoration-rose decoration-2 underline-offset-4"
              >
                {GHOST_PEONY_NAME}
              </a>{' '}
              for {PRODUCT_DOMAIN}.
            </p>
          </div>
          <SocialLinks tone="light" />
        </div>
      </footer>
    </div>
  );
}
