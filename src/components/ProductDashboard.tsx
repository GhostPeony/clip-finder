import React, { useEffect, useMemo, useState } from 'react';
import { PRODUCT_NAME } from '../brand';
import { IngestionJob, LibraryData, VideoClip } from '../types';
import { fetchIngestionJobs, fetchLibrary, fetchUsage, UsageInfo } from '../services/api';
import { UnifiedSearchView } from './UnifiedSearchView';

interface ProductDashboardProps {
  isBackendConnected: boolean;
  hasApiKey: boolean;
  hasServerKey: boolean;
  allowUserKeys: boolean;
  showLocalBackendHelp: boolean;
  onOpenSettings: () => void;
  onOpenLibrary: () => void;
  onOpenJobs: () => void;
  onSearchComplete: (clips: VideoClip[], answer: string, activeClip: VideoClip | null) => void;
  onIndexComplete: () => void;
}

export const ProductDashboard: React.FC<ProductDashboardProps> = ({
  isBackendConnected,
  hasApiKey,
  hasServerKey,
  allowUserKeys,
  showLocalBackendHelp,
  onOpenSettings,
  onOpenLibrary,
  onOpenJobs,
  onSearchComplete,
  onIndexComplete,
}) => {
  const [library, setLibrary] = useState<LibraryData | null>(null);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);

  useEffect(() => {
    let active = true;

    const loadDashboardData = async () => {
      const [libraryData, usageData, jobData] = await Promise.all([
        fetchLibrary(),
        fetchUsage(),
        fetchIngestionJobs(),
      ]);
      if (!active) return;
      setLibrary(libraryData);
      setUsage(usageData);
      setJobs(jobData.slice(0, 4));
    };

    loadDashboardData();
    const interval = window.setInterval(loadDashboardData, 15000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const recentStatus = useMemo(() => {
    const running = jobs.filter(
      (job) => job.status === 'running' || job.status === 'queued',
    ).length;
    const partial = jobs.filter((job) => job.status === 'partial').length;
    if (running > 0) return `${running} active import${running === 1 ? '' : 's'}`;
    if (partial > 0) return `${partial} partial import${partial === 1 ? '' : 's'}`;
    if (jobs.length > 0) return 'Imports settled';
    return 'Ready to index';
  }, [jobs]);

  return (
    <div className="space-y-8">
      <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="card glow-wash p-6 md:p-8">
          <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="eyebrow mb-3">{PRODUCT_NAME}</p>
              <h1 className="font-serif text-5xl font-medium leading-none tracking-tight md:text-6xl">
                Moment workbench
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-bark">
                Start with a link to build your library, or search what you have already indexed.
                Every result leads back to a verifiable timestamp.
              </p>
              <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2">
                <button onClick={onOpenLibrary} className="link-quiet text-sm">
                  Library
                </button>
                <button onClick={onOpenJobs} className="link-quiet text-sm">
                  Import jobs
                </button>
              </div>
            </div>
            <div className="grid grid-cols-3 divide-x divide-ink/10 rounded-xl bg-cream">
              <DashboardMetric value={library?.totalVideos ?? 0} label="videos" />
              <DashboardMetric value={library?.totalClips ?? 0} label="clips" />
              <DashboardMetric value={jobs.length} label="jobs" isLast />
            </div>
          </div>
        </div>

        <aside className="card p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Status</p>
          <div className="mt-5 space-y-2 text-sm font-medium">
            <StatusRow
              label="Service"
              value={isBackendConnected ? 'Ready' : 'Connecting'}
              tone={isBackendConnected ? 'good' : 'neutral'}
            />
            <StatusRow
              label="Model access"
              value={
                allowUserKeys ? (hasServerKey || hasApiKey ? 'Ready' : 'Needs setup') : 'Included'
              }
              tone={allowUserKeys && !hasServerKey && !hasApiKey ? 'warn' : 'good'}
            />
            <StatusRow label="Imports" value={recentStatus} tone="neutral" />
          </div>
          <button onClick={onOpenSettings} className="btn btn-secondary mt-5 w-full">
            Usage and settings
          </button>
        </aside>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="card p-4 md:p-6">
          <UnifiedSearchView
            onSearchComplete={onSearchComplete}
            onIndexComplete={onIndexComplete}
            isBackendConnected={isBackendConnected}
            hasApiKey={hasApiKey}
            hasServerKey={hasServerKey}
            allowUserKeys={allowUserKeys}
            showLocalBackendHelp={showLocalBackendHelp}
            onOpenSettings={onOpenSettings}
            maxSearchResults={usage?.maxSearchResults ?? 5}
          />
        </div>

        <div className="space-y-5">
          <DashboardPanel title="Library" accent="var(--peony-sun)">
            <p className="text-sm leading-6 text-bark">
              {library && library.totalVideos > 0
                ? `${library.totalVideos} videos across ${library.channels.length} channels are indexed.`
                : 'No videos indexed yet. Start with a channel, playlist, or single video URL.'}
            </p>
            <button onClick={onOpenLibrary} className="link-quiet mt-4 text-sm">
              Open library
            </button>
          </DashboardPanel>

          <DashboardPanel title="Usage" accent="var(--peony-mint)">
            <div className="space-y-3">
              <UsageBar
                label="Searches this month"
                used={usage?.searchesUsedThisMonth ?? 0}
                limit={usage?.searchLimit ?? null}
              />
              <UsageBar
                label="Videos indexed/accessed"
                used={usage?.indexedVideosUsed ?? 0}
                limit={usage?.indexedVideoLimit ?? null}
              />
              <UsageBar
                label="Transcript hours"
                used={secondsToHours(usage?.indexedSecondsUsed ?? 0)}
                limit={
                  usage?.indexedSecondsLimit ? secondsToHours(usage.indexedSecondsLimit) : null
                }
                displayValue={
                  usage?.indexedSecondsLimit
                    ? `${secondsToHours(usage.indexedSecondsUsed).toFixed(1)}/${secondsToHours(
                        usage.indexedSecondsLimit,
                      ).toFixed(1)}h`
                    : `${secondsToHours(usage?.indexedSecondsUsed ?? 0).toFixed(1)}h/unlimited`
                }
              />
            </div>
          </DashboardPanel>

          <DashboardPanel title="Recent jobs" accent="var(--peony-rose)">
            {jobs.length === 0 ? (
              <p className="text-sm leading-6 text-bark">No ingestion jobs yet.</p>
            ) : (
              <div className="space-y-3">
                {jobs.map((job) => (
                  <div key={job.id} className="rounded-xl bg-cream p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold uppercase tracking-wide text-violet-deep">
                        {job.status}
                      </span>
                      <span className="text-xs font-medium text-muted">
                        {job.indexed_video_count} indexed
                      </span>
                    </div>
                    <p className="mt-2 truncate text-xs text-bark">
                      {job.last_message || job.source_url}
                    </p>
                  </div>
                ))}
              </div>
            )}
            <button onClick={onOpenJobs} className="link-quiet mt-4 text-sm">
              View jobs
            </button>
          </DashboardPanel>
        </div>
      </section>
    </div>
  );
};

function DashboardMetric({
  value,
  label,
  isLast = false,
}: {
  value: number;
  label: string;
  isLast?: boolean;
}) {
  return (
    <div className={`min-w-20 p-4 text-center ${isLast ? '' : ''}`}>
      <p className="font-serif text-2xl font-medium text-rose-deep">{value}</p>
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
    </div>
  );
}

function StatusRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'good' | 'warn' | 'bad' | 'neutral';
}) {
  const chipClass =
    tone === 'good'
      ? 'chip chip-leaf'
      : tone === 'warn'
        ? 'chip chip-sun'
        : tone === 'bad'
          ? 'chip'
          : 'chip chip-violet';

  return (
    <div className="flex items-center justify-between rounded-xl bg-cream px-3 py-2">
      <span>{label}</span>
      <span className={chipClass}>{value}</span>
    </div>
  );
}

function DashboardPanel({
  title,
  accent,
  children,
}: {
  title: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card p-5">
      <div className="mb-4 flex items-center gap-2.5">
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: accent }} />
        <h2 className="font-serif text-2xl font-medium">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function UsageBar({
  label,
  used,
  limit,
  displayValue,
}: {
  label: string;
  used: number;
  limit: number | null;
  displayValue?: string;
}) {
  const percent = limit && limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 12;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3 text-xs font-medium text-muted">
        <span>{label}</span>
        <span>{displayValue || (limit ? `${used}/${limit}` : `${used}/unlimited`)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-petal">
        <div className="h-full rounded-full bg-teal" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function secondsToHours(seconds: number): number {
  return seconds / 3600;
}
