import type { CSSProperties } from 'react';
import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { GHOST_PEONY_NAME, GHOST_PEONY_URL, PRODUCT_DOMAIN, PRODUCT_NAME } from '../brand';
import { BrandLogo } from './BrandLogo';
import { SocialLinks } from './SocialLinks';

const workflowSteps = [
  [
    '01',
    'Save the video',
    'Keep browsing. Save the video to a linked playlist or add the URL to the dashboard, even if you do not have time to watch it yet.',
  ],
  [
    '02',
    'Memexai breaks it down',
    'Captions become a video breakdown: timestamped moments, key ideas, summaries, and links back to the exact parts of the video.',
  ],
  [
    '03',
    'Use it as memory',
    'Search from the dashboard, read TLDRs and reports, or let an agent work from the same structured video context.',
  ],
];

const useCases = [
  [
    'Learn from chosen sources',
    'For online lectures, podcasts you love, tutorials, or any channel you follow, start from videos you saved instead of sending an agent into a broad web search.',
  ],
  [
    'Catch up later',
    'Turn a backlog of promising videos into TLDRs, source-backed notes, and questions to revisit when you have time.',
  ],
  [
    'Connect your agent',
    'Use MCP when you want Claude, Codex, Hermes, or any agent to search concepts, summaries, notes, and timestamped clips.',
  ],
  [
    'Read source reports',
    'Turn lectures, explainers, tutorials, interviews, and talks into TLDRs, timestamped topics, and source-backed reports without filling your session context.',
  ],
  [
    'Draft from video context',
    'Pull product ideas, workflows, implementation notes, research concepts, or daily reports from the videos you already selected.',
  ],
];

interface LandingPageProps {
  onOpenDashboard?: () => void;
}

function MomentVignette() {
  return (
    <div className="card p-6 sm:p-8" aria-hidden="true">
      <p className="font-serif text-2xl font-medium text-ink">
        Saved video becomes structured knowledge
      </p>
      <div className="mt-5 space-y-3">
        {[
          ['Source-linked clips', 'Important ideas stay tied to the exact part of the video.'],
          [
            'Timestamped topics',
            'Concepts, claims, people, tools, and methods link back to evidence.',
          ],
          ['Reports', 'TLDRs, source reports, briefs, and personal notes build on the source.'],
        ].map(([title, body]) => (
          <div key={title} className="rounded-xl bg-cream p-4">
            <p className="text-sm font-semibold text-ink">{title}</p>
            <p className="mt-1 text-xs leading-5 text-bark">{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function LandingPage({ onOpenDashboard }: LandingPageProps = {}) {
  const { signInWithGoogle, user } = useAuth();
  const [googleLoading, setGoogleLoading] = useState(false);
  const [authError, setAuthError] = useState('');
  const [videoMuted, setVideoMuted] = useState(true);
  const [videoPaused, setVideoPaused] = useState(false);
  const [reduceVideoMotion, setReduceVideoMotion] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const videoStageRef = useRef<HTMLElement | null>(null);
  const videoInViewRef = useRef(true);
  const userPausedVideoRef = useRef(false);

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

  useEffect(() => {
    const stage = videoStageRef.current;
    if (!stage || !('requestAnimationFrame' in window)) return;

    let frameId = 0;
    const updateProgress = () => {
      frameId = 0;
      const rect = stage.getBoundingClientRect();
      const distance = Math.max(1, rect.height);
      const progress = Math.min(1, Math.max(0, -rect.top / distance));
      stage.style.setProperty('--video-scroll-progress', progress.toFixed(3));
    };

    const requestUpdate = () => {
      if (frameId) return;
      frameId = window.requestAnimationFrame(updateProgress);
    };

    updateProgress();
    window.addEventListener('scroll', requestUpdate, { passive: true });
    window.addEventListener('resize', requestUpdate);
    return () => {
      window.removeEventListener('scroll', requestUpdate);
      window.removeEventListener('resize', requestUpdate);
      if (frameId) window.cancelAnimationFrame(frameId);
    };
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    const stage = videoStageRef.current;
    if (!video || !stage) return;

    const motionQuery =
      typeof window.matchMedia === 'function'
        ? window.matchMedia('(prefers-reduced-motion: reduce)')
        : null;

    const syncPlayback = () => {
      const shouldPause =
        Boolean(motionQuery?.matches) ||
        document.hidden ||
        !videoInViewRef.current ||
        userPausedVideoRef.current;
      if (shouldPause) {
        video.pause();
        setVideoPaused(true);
        return;
      }

      try {
        const playPromise = video.play();
        void playPromise
          .then(() => setVideoPaused(false))
          .catch(() => {
            setVideoPaused(true);
            // Autoplay may be blocked in some browsers; the user can still start it manually.
          });
      } catch {
        setVideoPaused(true);
      }
    };

    const handleMotionChange = () => {
      setReduceVideoMotion(Boolean(motionQuery?.matches));
      syncPlayback();
    };

    if (!('IntersectionObserver' in window)) {
      setReduceVideoMotion(Boolean(motionQuery?.matches));
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        videoInViewRef.current = entry.isIntersecting;
        syncPlayback();
      },
      { threshold: 0.1 },
    );

    setReduceVideoMotion(Boolean(motionQuery?.matches));
    observer.observe(stage);
    document.addEventListener('visibilitychange', syncPlayback);
    motionQuery?.addEventListener('change', handleMotionChange);
    syncPlayback();

    return () => {
      observer.disconnect();
      document.removeEventListener('visibilitychange', syncPlayback);
      motionQuery?.removeEventListener('change', handleMotionChange);
    };
  }, []);

  const openDashboard = () => {
    setAuthError('');
    if (onOpenDashboard) {
      onOpenDashboard();
      return;
    }
    window.location.assign('/');
  };

  const handlePrimaryAction = async () => {
    if (user) {
      openDashboard();
      return;
    }
    setGoogleLoading(true);
    setAuthError('');
    const { error } = await signInWithGoogle();
    if (error) {
      setAuthError(error.message);
      setGoogleLoading(false);
    }
  };

  const handleVideoAudioToggle = async () => {
    const video = videoRef.current;
    if (!video) return;
    const nextMuted = !video.muted;
    video.muted = nextMuted;
    setVideoMuted(nextMuted);
    if (!nextMuted) {
      try {
        if (!userPausedVideoRef.current) {
          await video.play();
          setVideoPaused(false);
        }
      } catch {
        video.muted = true;
        setVideoMuted(true);
      }
    }
  };

  const handleVideoPlaybackToggle = async () => {
    const video = videoRef.current;
    if (!video) return;

    if (video.paused) {
      userPausedVideoRef.current = false;
      try {
        await video.play();
        setVideoPaused(false);
      } catch {
        userPausedVideoRef.current = true;
        setVideoPaused(true);
      }
      return;
    }

    userPausedVideoRef.current = true;
    video.pause();
    setVideoPaused(true);
  };

  const primaryLabel = user ? 'Open dashboard' : googleLoading ? 'Redirecting...' : 'Start free';
  const headerLabel = user ? 'Dashboard' : googleLoading ? 'Redirecting...' : 'Login';
  const primaryDisabled = !user && googleLoading;

  return (
    <div className="landing-page min-h-screen overflow-hidden bg-cream text-ink">
      <header className="landing-reveal fixed top-0 z-50 w-full border-b border-ink/10 bg-cream/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
          <BrandLogo size="sm" />
          <nav className="hidden items-center gap-8 text-sm font-medium text-bark md:flex">
            <a href="#workflow" className="transition-colors hover:text-ink">
              How it works
            </a>
            <a href="#proof" className="transition-colors hover:text-ink">
              Tools
            </a>
            <a href="#use-cases" className="transition-colors hover:text-ink">
              Use cases
            </a>
          </nav>
          <button
            onClick={handlePrimaryAction}
            disabled={primaryDisabled}
            className="btn btn-primary min-h-10 whitespace-nowrap px-4 py-2 text-sm sm:px-6"
          >
            {headerLabel}
          </button>
        </div>
      </header>

      <main className="pt-16">
        <section
          ref={videoStageRef}
          className="landing-video-stage"
          aria-label="Memexai promo video"
        >
          <div className="landing-video-panel">
            <video
              ref={videoRef}
              className="landing-video-panel-video"
              src="/videos/memexai-groove-v1.mp4"
              autoPlay={!reduceVideoMotion}
              muted={videoMuted}
              loop
              playsInline
              preload="metadata"
            />
            <div className="landing-video-controls">
              <button
                type="button"
                className="landing-video-control"
                onClick={() => void handleVideoPlaybackToggle()}
                aria-pressed={!videoPaused}
                aria-label={videoPaused ? 'Play promo video' : 'Pause promo video'}
              >
                {videoPaused ? 'Play' : 'Pause'}
              </button>
              <button
                type="button"
                className="landing-video-control"
                onClick={() => void handleVideoAudioToggle()}
                aria-pressed={!videoMuted}
                aria-label={videoMuted ? 'Unmute promo video' : 'Mute promo video'}
              >
                {videoMuted ? 'Unmute' : 'Mute'}
              </button>
            </div>
          </div>
        </section>

        <section className="glow-wash relative">
          <div className="mx-auto max-w-6xl px-5 pb-24 pt-20 sm:pt-28 md:pb-32 md:pt-36">
            <div className="max-w-4xl">
              <h1
                className="landing-reveal font-serif text-5xl font-medium leading-[1.02] tracking-tight sm:text-7xl md:text-8xl"
                style={{ '--reveal-delay': '0.1s' } as CSSProperties}
              >
                Video memory for you and your agent .
              </h1>
              <p
                className="landing-reveal mt-8 max-w-2xl text-lg leading-8 text-bark md:text-xl"
                style={{ '--reveal-delay': '0.3s' } as CSSProperties}
              >
                Link a YouTube playlist, save videos as you browse. Memexai turns them into a
                private, searchable context library for you and your agent.
              </p>
              <div
                className="landing-reveal mt-10 flex flex-col items-start gap-5 sm:flex-row sm:items-center"
                style={{ '--reveal-delay': '0.5s' } as CSSProperties}
              >
                <button
                  onClick={handlePrimaryAction}
                  disabled={primaryDisabled}
                  className="btn btn-primary px-8 py-3 text-base"
                >
                  {primaryLabel}
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
                Turn video content into a useful video breakdown.
              </h2>
              <p className="max-w-xl text-base leading-7 text-bark">
                Memexai turns videos into timestamped moments, topics, reports, notes, and timestamp
                links so your agent can pull from videos you already chose.
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
                Your saved videos are the research corpus.
              </h2>
              <p className="mt-6 max-w-md text-base leading-7 text-bark">
                When a topic matters, web search can be too broad and a pasted YouTube link makes
                every agent start over. Memexai keeps the useful videos you picked ready for search,
                summaries, prompts, briefs, and lessons.
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
                Put everything you save to work.
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
              Ingest the video once. Stop pasting it into your AI chatbox.
            </h2>
            <p className="mx-auto mt-6 max-w-xl text-base leading-7 text-bark md:text-lg">
              Free to start. Link a playlist, add videos, and give yourself a video memory your
              agent can actually use.
            </p>
            <div className="mt-10 flex justify-center">
              <button
                onClick={handlePrimaryAction}
                disabled={primaryDisabled}
                className="btn btn-primary px-8 py-3 text-base"
              >
                {primaryLabel}
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
              A searchable memory for saved YouTube videos, timestamps, ideas, and notes. Built by{' '}
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
