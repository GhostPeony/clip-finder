import React, { useState, useEffect } from 'react';
import {
  saveApiKey,
  createCaptureSource,
  createBillingCheckout,
  createBillingPortal,
  deleteApiKey,
  deleteCaptureSource,
  disconnectYoutubeOAuth,
  createMcpToken,
  fetchCaptureSources,
  fetchMcpTokens,
  fetchUsage,
  fetchYoutubeOAuthStatus,
  getAgentFullGuideUrl,
  getAgentGuideUrl,
  getMcpManifestUrl,
  getMcpServerUrl,
  getStoredLocalApiKey,
  revokeMcpToken,
  syncCaptureSource,
  UsageInfo,
} from '../services/api';
import {
  CaptureSource,
  CreatedMcpToken,
  McpSetupBundle,
  McpTokenRecord,
  YoutubeOAuthStatus,
} from '../types';
import { YOUTUBE_CONNECTION_SAVED_EVENT } from '../contexts/AuthContext';
import { CaptureSourceDisconnectModal } from './CaptureSourceDisconnectModal';
import { CaptureSyncConfirmModal } from './CaptureSyncConfirmModal';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  allowUserKeys?: boolean;
  onConnectYouTube?: () => Promise<{ error: { message?: string } | null }>;
}

// Keep for backward compat during migration -- App.tsx still references this
export const getStoredApiKey = (): string | null => {
  return getStoredLocalApiKey();
};

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  allowUserKeys = true,
  onConnectYouTube,
}) => {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [usageUnavailable, setUsageUnavailable] = useState(false);
  const [settingsView, setSettingsView] = useState<'settings' | 'plans'>('settings');

  const refreshUsage = async () => {
    try {
      const info = await fetchUsage();
      setUsage(info);
      setUsageUnavailable(false);
    } catch {
      setUsage(null);
      setUsageUnavailable(true);
    }
  };

  useEffect(() => {
    if (isOpen) {
      setApiKey('');
      setSaved(false);
      setSettingsView('settings');
      void refreshUsage();
    }
  }, [isOpen]);

  const handleSave = async () => {
    if (!apiKey.trim()) return;
    setSaving(true);
    const success = await saveApiKey(apiKey.trim());
    setSaving(false);
    if (success) {
      setSaved(true);
      void refreshUsage();
      setTimeout(() => onClose(), 1000);
    }
  };

  const handleClear = async () => {
    setSaving(true);
    await deleteApiKey();
    setSaving(false);
    setApiKey('');
    setSaved(true);
    void refreshUsage();
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 px-4 py-4 backdrop-blur-sm"
      onClick={onClose}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={settingsView === 'plans' ? 'Choose a paid plan' : 'Settings'}
        className="card max-h-[calc(100vh-2rem)] w-full max-w-4xl overflow-y-auto p-4 shadow-lift sm:p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between gap-4 border-b border-ink/10 pb-4">
          <div className="min-w-0">
            {settingsView === 'plans' ? (
              <button
                type="button"
                onClick={() => setSettingsView('settings')}
                className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted hover:text-ink"
              >
                Back to settings
              </button>
            ) : null}
            <h2 className="font-serif text-3xl font-medium text-ink">
              {settingsView === 'plans' ? 'Choose a plan' : 'Settings'}
            </h2>
            <p className="mt-1 text-sm text-bark">
              {settingsView === 'plans'
                ? 'Compare limits and billing cadence before Stripe opens.'
                : 'Manage YouTube capture, usage, and account access.'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 text-bark transition-colors hover:bg-cream hover:text-ink"
            title="Close settings"
            aria-label="Close settings"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {settingsView === 'plans' ? (
          <PlanSelectionView
            currentPlan={usage?.planKey || usage?.plan || 'free'}
            onBack={() => setSettingsView('settings')}
          />
        ) : (
          <>
            <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(17rem,20rem)]">
              <CaptureSourcesSection onConnectYouTube={onConnectYouTube} />
              <UsageQuotaCard
                usage={usage}
                unavailable={usageUnavailable}
                onUpgrade={() => setSettingsView('plans')}
              />
            </div>

            <div className="mt-4 space-y-4">
              {allowUserKeys ? (
                <section className="rounded-xl border border-ink/10 bg-surface p-4">
                  <label className="mb-1 block text-sm font-semibold text-ink">
                    Gemini API Key{' '}
                    {usage?.hasOwnKey && (
                      <span className="font-normal text-leaf-deep">(active)</span>
                    )}
                  </label>
                  <p className="mb-2 text-xs text-bark">
                    Use your Gemini key for model processing where enabled. Hosted plan limits still
                    apply to storage, imports, and retrieval. Get one from{' '}
                    <a
                      href="https://aistudio.google.com/app/apikey"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-semibold text-violet-deep underline decoration-2 underline-offset-4"
                    >
                      Google AI Studio
                    </a>
                  </p>
                  <div className="relative">
                    <input
                      type={showKey ? 'text' : 'password'}
                      value={apiKey}
                      onChange={(e) => {
                        setApiKey(e.target.value);
                        setSaved(false);
                      }}
                      placeholder={usage?.hasOwnKey ? '(key stored securely)' : 'AIza...'}
                      className="input w-full px-3 py-2 pr-10 text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey(!showKey)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-ink"
                      aria-label={showKey ? 'Hide API key' : 'Show API key'}
                    >
                      {showKey ? (
                        <svg
                          className="w-5 h-5"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                          />
                        </svg>
                      ) : (
                        <svg
                          className="w-5 h-5"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                          />
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                          />
                        </svg>
                      )}
                    </button>
                  </div>

                  <div className="mt-4 border-t border-ink/10 pt-3 text-xs leading-5 text-ink">
                    <strong>Security:</strong> Your key is encrypted before storage and never
                    displayed again.
                  </div>
                </section>
              ) : null}

              <AgentAccessSection />
            </div>

            <div className={`mt-6 flex ${allowUserKeys ? 'justify-between' : 'justify-end'}`}>
              {allowUserKeys ? (
                <button
                  onClick={handleClear}
                  disabled={saving}
                  className="px-3 py-2 text-sm font-medium text-muted hover:text-rose-deep disabled:opacity-50"
                >
                  Remove Key
                </button>
              ) : null}
              <div className="flex gap-2">
                <button onClick={onClose} className="btn btn-secondary min-h-0 px-4 py-2 text-sm">
                  Cancel
                </button>
                {allowUserKeys && (
                  <button
                    onClick={handleSave}
                    disabled={saving || !apiKey.trim()}
                    className="btn btn-primary min-h-0 px-4 py-2 text-sm"
                  >
                    {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Key'}
                  </button>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default SettingsModal;

function secondsToHours(seconds: number): number {
  return seconds / 3600;
}

type BillingInterval = 'monthly' | 'annual';
type UpgradePlanKey = 'plus' | 'pro';

const PLAN_LOOKUP_KEYS: Record<UpgradePlanKey, Record<BillingInterval, string>> = {
  plus: {
    monthly: 'memexai_plus_monthly_v1',
    annual: 'memexai_plus_annual_v1',
  },
  pro: {
    monthly: 'memexai_pro_monthly_v1',
    annual: 'memexai_pro_annual_v1',
  },
};

const UPGRADE_PLANS: Array<{
  key: UpgradePlanKey;
  name: string;
  monthlyPrice: string;
  annualPrice: string;
  annualNote: string;
  summary: string;
  details: string[];
}> = [
  {
    key: 'plus',
    name: 'Plus',
    monthlyPrice: '$12/mo',
    annualPrice: '$120/yr',
    annualNote: '2 months included',
    summary: 'For a focused personal video memory.',
    details: [
      '50 new transcript hours each month',
      '500 total transcript hours in your library',
      '2,000 monthly searches',
      '25 videos per import',
    ],
  },
  {
    key: 'pro',
    name: 'Pro',
    monthlyPrice: '$29/mo',
    annualPrice: '$288/yr',
    annualNote: 'about $24/mo',
    summary: 'For larger libraries and heavier agent use.',
    details: [
      '200 new transcript hours each month',
      '2,000 total transcript hours in your library',
      '10,000 monthly searches',
      'Priority queue and 100 videos per import',
    ],
  },
];

function PlanSelectionView({ currentPlan, onBack }: { currentPlan: string; onBack: () => void }) {
  const [billingBusy, setBillingBusy] = useState<string | null>(null);
  const [billingError, setBillingError] = useState<string | null>(null);
  const [billingInterval, setBillingInterval] = useState<BillingInterval>('monthly');

  const openCheckout = async (planKey: UpgradePlanKey) => {
    const lookupKey = PLAN_LOOKUP_KEYS[planKey][billingInterval];
    setBillingBusy(`${planKey}-${billingInterval}`);
    setBillingError(null);
    try {
      window.location.href = await createBillingCheckout(lookupKey);
    } catch (error) {
      setBillingError(error instanceof Error ? error.message : 'Could not open Stripe Checkout.');
      setBillingBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-ink/10 bg-surface p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              Current plan: {currentPlan.replace(/^\w/, (char) => char.toUpperCase())}
            </p>
            <h3 className="mt-1 font-serif text-3xl font-medium text-ink">Paid plans</h3>
          </div>
          <div className="inline-flex rounded-lg border border-ink/10 bg-cream p-1">
            {(['monthly', 'annual'] as BillingInterval[]).map((interval) => (
              <button
                key={interval}
                type="button"
                onClick={() => setBillingInterval(interval)}
                className={`rounded-md px-3 py-1.5 text-xs font-semibold capitalize transition-colors ${
                  billingInterval === interval
                    ? 'bg-surface text-ink shadow-soft'
                    : 'text-bark hover:text-ink'
                }`}
                aria-pressed={billingInterval === interval}
              >
                {interval}
              </button>
            ))}
          </div>
        </div>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-bark">
          Pick the plan that matches your video library. Stripe opens only after you choose a plan
          and cadence.
        </p>
        {billingError ? (
          <p className="mt-3 rounded-lg bg-petal px-3 py-2 text-xs font-medium leading-5 text-rose-deep">
            {billingError}
          </p>
        ) : null}
      </section>

      <div className="grid gap-3 md:grid-cols-2">
        {UPGRADE_PLANS.map((plan) => {
          const price = billingInterval === 'monthly' ? plan.monthlyPrice : plan.annualPrice;
          const busyKey = `${plan.key}-${billingInterval}`;
          return (
            <section key={plan.key} className="rounded-xl border border-ink/10 bg-surface p-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h4 className="font-serif text-3xl font-medium text-ink">{plan.name}</h4>
                  <p className="mt-1 text-sm leading-6 text-bark">{plan.summary}</p>
                </div>
                <div className="shrink-0 text-left sm:text-right">
                  <p className="font-mono text-xl font-semibold text-ink">{price}</p>
                  <p className="text-[11px] font-medium text-muted">
                    {billingInterval === 'annual' ? plan.annualNote : 'billed monthly'}
                  </p>
                </div>
              </div>
              <ul className="mt-4 space-y-2">
                {plan.details.map((detail) => (
                  <li key={detail} className="rounded-lg bg-cream px-3 py-2 text-sm text-bark">
                    {detail}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                onClick={() => openCheckout(plan.key)}
                disabled={billingBusy !== null}
                className={`mt-4 w-full min-h-0 px-3 py-2 text-sm ${
                  plan.key === 'plus' ? 'btn btn-primary' : 'btn btn-secondary'
                }`}
              >
                {billingBusy === busyKey ? `Opening ${plan.name}...` : `Continue with ${plan.name}`}
              </button>
            </section>
          );
        })}
      </div>

      <div className="flex flex-col gap-3 border-t border-ink/10 pt-4 sm:flex-row sm:justify-between">
        <button
          type="button"
          onClick={onBack}
          className="btn btn-secondary min-h-0 self-start px-4 py-2 text-sm"
        >
          Back
        </button>
        <p className="max-w-md text-left text-xs leading-5 text-muted sm:text-right">
          Plan changes are handled by Stripe. You can return here later to manage billing or cancel.
        </p>
      </div>
    </div>
  );
}

function UsageQuotaCard({
  usage,
  unavailable = false,
  onUpgrade,
}: {
  usage: UsageInfo | null;
  unavailable?: boolean;
  onUpgrade: () => void;
}) {
  const [billingBusy, setBillingBusy] = useState<string | null>(null);
  const [billingError, setBillingError] = useState<string | null>(null);

  if (usage === null && unavailable) {
    return (
      <section className="min-w-0 rounded-xl border border-ink/10 bg-surface p-4">
        <h3 className="font-serif text-2xl font-medium text-ink">Usage</h3>
        <p className="mt-3 text-sm text-bark">Usage unavailable</p>
        <p className="mt-1 text-xs leading-5 text-muted">
          We could not load your usage right now. Close and reopen settings to retry.
        </p>
      </section>
    );
  }

  if (usage === null) {
    return (
      <section className="min-w-0 rounded-xl border border-ink/10 bg-surface p-4">
        <h3 className="font-serif text-2xl font-medium text-ink">Usage</h3>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
          {['Searches', 'Videos', 'Transcript hours', 'Import size'].map((label) => (
            <div key={label} className="rounded-xl bg-cream p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
              <p className="mt-1 font-mono text-sm font-semibold text-bark">Checking</p>
            </div>
          ))}
        </div>
      </section>
    );
  }

  const formatCount = (used: number | null | undefined, limit: number | null | undefined) => {
    const usedLabel = used ?? 0;
    return limit === null || limit === undefined
      ? `${usedLabel} / unlimited`
      : `${usedLabel} / ${limit}`;
  };

  const formatHours = (used: number | null | undefined, limit: number | null | undefined) => {
    const usedHours = secondsToHours(used ?? 0).toFixed(1);
    if (limit === null || limit === undefined) return `${usedHours}h / unlimited`;
    return `${usedHours} / ${secondsToHours(limit).toFixed(1)}h`;
  };

  const metrics = [
    {
      label: 'Searches',
      value: formatCount(usage.searchesUsedThisMonth, usage.searchLimit),
    },
    {
      label: 'New transcript hours',
      value: formatHours(
        usage.monthlyIndexedSecondsUsed ?? usage.indexedSecondsUsed,
        usage.monthlyIndexedSecondsLimit ?? usage.indexedSecondsLimit,
      ),
    },
    {
      label: 'Total library',
      value: formatHours(usage.indexedSecondsUsed, usage.indexedSecondsLimit),
    },
    {
      label: 'Videos',
      value: formatCount(usage.indexedVideosUsed, usage.indexedVideoLimit),
    },
    {
      label: 'Import size',
      value: usage.maxImportVideos ? `${usage.maxImportVideos} videos` : 'Checking',
    },
  ];

  const activePlanKey = usage.planKey || usage.plan || 'free';
  const planLabel = activePlanKey.replace(/^\w/, (char) => char.toUpperCase());
  const isPaidPlan = activePlanKey === 'plus' || activePlanKey === 'pro';
  const billingNote =
    usage.billingStatus === 'past_due'
      ? 'Payment needs attention. New imports and high-volume retrieval use Free limits until billing is current.'
      : usage.cancelAtPeriodEnd && usage.currentPeriodEnd
        ? `Cancels at period end: ${new Date(usage.currentPeriodEnd).toLocaleDateString()}`
        : null;

  const openBillingPortal = async () => {
    setBillingBusy('portal');
    setBillingError(null);
    try {
      window.location.href = await createBillingPortal();
    } catch (error) {
      setBillingError(error instanceof Error ? error.message : 'Could not open billing portal.');
      setBillingBusy(null);
    }
  };

  return (
    <section className="min-w-0 rounded-xl border border-ink/10 bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-serif text-2xl font-medium text-ink">Usage</h3>
          <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-muted">
            {planLabel} plan
          </p>
        </div>
        {isPaidPlan ? (
          <button
            type="button"
            onClick={() => openBillingPortal()}
            disabled={billingBusy !== null}
            className="btn btn-secondary min-h-0 px-3 py-2 text-xs"
          >
            {billingBusy === 'portal' ? 'Opening...' : 'Manage billing'}
          </button>
        ) : (
          <button
            type="button"
            onClick={onUpgrade}
            className="btn btn-primary min-h-0 px-3 py-2 text-xs"
          >
            Upgrade
          </button>
        )}
      </div>
      {billingNote ? <p className="mt-2 text-xs leading-5 text-rose-deep">{billingNote}</p> : null}
      {billingError ? (
        <p className="mt-2 text-xs leading-5 text-rose-deep">{billingError}</p>
      ) : null}
      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
        {metrics.map((metric) => (
          <div key={metric.label} className="min-w-0 rounded-xl bg-cream p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              {metric.label}
            </p>
            <p className="mt-1 break-words font-mono text-sm font-semibold text-ink">
              {metric.value}
            </p>
          </div>
        ))}
      </div>
      {usage.searchLimit ? (
        <div className="mt-3">
          <div className="h-2 overflow-hidden rounded-full bg-petal">
            <div
              className="h-full rounded-full bg-teal transition-all"
              style={{
                width: `${Math.min(100, (usage.searchesUsedThisMonth / usage.searchLimit) * 100)}%`,
              }}
            />
          </div>
        </div>
      ) : null}
    </section>
  );
}

function formatYouTubeConnectionStatus(status: YoutubeOAuthStatus): string {
  if (!status.connected) return 'Not connected yet.';
  if (!status.youtubeReadonlyGranted) return 'Connected, but YouTube read access is missing.';
  if (!status.hasRefreshToken) return 'Reconnect to keep playlist sync running.';
  return 'Connected with YouTube read access.';
}

type McpTokenState =
  | { status: 'loading' }
  | { status: 'ready'; tokens: McpTokenRecord[] }
  | { status: 'error'; message: string; tokens: McpTokenRecord[] };

type CaptureSourceState =
  | { status: 'loading' }
  | { status: 'ready'; sources: CaptureSource[] }
  | { status: 'error'; message: string; sources: CaptureSource[] };

interface PendingCaptureSync {
  source: CaptureSource;
  pendingCount: number;
}

const DEFAULT_MCP_TOKEN_NAME = 'My MCP agent';

function buildLocalMcpSetupBundle(
  mcpServerUrl: string,
  mcpManifestUrl: string,
  agentGuideUrl: string,
  agentFullGuideUrl: string,
  token?: string,
): McpSetupBundle {
  const tokenEnvironmentVariable = 'MEMEXAI_MCP_TOKEN';
  const claudeSetupSteps = [
    'Open Claude settings, then Customize > Connectors.',
    'Choose Add custom connector and paste the Memexai MCP URL.',
    'Name it Memexai, finish adding it, then click Connect.',
    'Sign in with Google, approve Memexai access, and enable the connector in the chat.',
  ];
  const claudeInitialPrompt =
    'Use my Memexai connector. Start with get_mcp_session, then list_projects. If a project matches my task, open its project context map before searching source reports or transcript moments.';
  const hermesConfig = [
    'mcp_servers:',
    '  memexai:',
    `    url: "${mcpServerUrl}"`,
    '    headers:',
    `      Authorization: "Bearer \${${tokenEnvironmentVariable}}"`,
    '    timeout: 180',
    '    connect_timeout: 30',
  ].join('\n');
  const codexConfig = [
    '[mcp_servers.memexai]',
    `url = "${mcpServerUrl}"`,
    `bearer_token_env_var = "${tokenEnvironmentVariable}"`,
    'startup_timeout_sec = 20',
    'tool_timeout_sec = 120',
  ].join('\n');
  const firstSteps = [
    'Call get_mcp_session to confirm token scopes, owner context, and safe next calls.',
    'Call get_agent_quickstart or read context://agent-quickstart.',
    'Call list_video_library or read context://library before searching.',
    'Call list_context_categories or read context://categories when you need filters.',
    'Use search_transcript_text first for exact phrases, names, acronyms, and product terms.',
    'Use search_video_concepts for cheap concepts, TLDRs, source reports, methods, tools, and pitfalls before pulling timestamp clips.',
    'Use get_repo_context_workflow or read context://repo-context-workflow for the repo-via-MCP collection flow.',
    'Use get_repo_context_contract or read context://repo-context-contract for the expected repo_context shape.',
    "Optional: use prompts/get collect_repo_context to gather repo_context with the agent's own repo MCP.",
    'Call validate_repo_context and follow readiness.suggestedAgentNextSteps before implementation planning.',
    'Use search_video_moments with retrieval_mode=hybrid for timestamp evidence and inspect accessScope/accessReason.',
    'Call build_agent_brief with a query and validated repo_context.',
  ];
  return {
    serverName: 'memexai',
    mcpEndpoint: mcpServerUrl,
    manifestUrl: mcpManifestUrl,
    agentGuideUrl,
    fullAgentGuideUrl: agentFullGuideUrl,
    claudeCustomConnector: {
      name: 'Memexai',
      url: mcpServerUrl,
      setupSteps: claudeSetupSteps,
      initialPrompt: claudeInitialPrompt,
      authMode: 'Remote MCP OAuth through Google sign-in and Memexai approval.',
      fallback:
        'If the Claude client cannot complete OAuth, create a scoped MCP token below and use a client that supports bearer-token MCP headers.',
    },
    tokenEnvironmentVariable,
    hermesConfig,
    codexConfig,
    codexSetupNote:
      'Add this to ~/.codex/config.toml and set MEMEXAI_MCP_TOKEN where Codex runs. Codex uses your own Codex or API-key auth; Memexai does not spend your Codex subscription from hosted servers.',
    firstSteps,
    firstCalls: [
      {
        tool: 'get_mcp_session',
        purpose: 'Confirm effective scopes and the MCP token owner context.',
      },
      {
        tool: 'get_agent_quickstart',
        purpose: 'Load the recommended workflow for the connected agent.',
      },
      {
        tool: 'list_video_library',
        purpose: 'Inspect only the videos granted to this user before searching.',
      },
      {
        tool: 'search_video_concepts',
        purpose:
          'Search extracted concepts and generated artifacts without embedding or LLM spend.',
      },
      {
        tool: 'search_video_moments',
        purpose:
          'Retrieve hybrid, semantic, or keyword timestamped evidence from user-granted videos.',
      },
    ],
    accessModel: {
      searchScope: 'current_user_grants',
      globalSearch: 'not_exposed',
      visibilityGrants: ['user_videos', 'user_channels'],
      canonicalStorage: 'Videos and transcript-derived context are stored once per YouTube video.',
      dedupeBehavior:
        "Already-indexed videos are attached to the user's library with an access grant instead of re-embedding duplicate chunks.",
      agentInstruction:
        'Use only results returned through the current MCP token and preserve accessScope/accessReason when explaining provenance.',
    },
    ...(token
      ? {
          oneTimeCredential: {
            bearerToken: token,
            envLine: `${tokenEnvironmentVariable}=${token}`,
            codexEnvLine: `${tokenEnvironmentVariable}=${token}`,
            hermesConfig: hermesConfig.replace(`\${${tokenEnvironmentVariable}}`, token),
          },
        }
      : {}),
  };
}

const CaptureSourcesSection: React.FC<{
  onConnectYouTube?: () => Promise<{ error: { message?: string } | null }>;
}> = ({ onConnectYouTube }) => {
  const [sourceState, setSourceState] = useState<CaptureSourceState>({ status: 'loading' });
  const [playlistUrl, setPlaylistUrl] = useState('');
  const [sourceTitle, setSourceTitle] = useState('Memexai Inbox');
  const [creating, setCreating] = useState(false);
  const [syncingSourceId, setSyncingSourceId] = useState<string | null>(null);
  const [pendingSync, setPendingSync] = useState<PendingCaptureSync | null>(null);
  const [confirmingSync, setConfirmingSync] = useState(false);
  const [pendingDisconnectSource, setPendingDisconnectSource] = useState<CaptureSource | null>(
    null,
  );
  const [disconnectingSourceId, setDisconnectingSourceId] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [youtubeStatus, setYoutubeStatus] = useState<YoutubeOAuthStatus | null>(null);
  const [connectingYouTube, setConnectingYouTube] = useState(false);
  const [disconnectingYouTube, setDisconnectingYouTube] = useState(false);
  const [youtubeMessage, setYoutubeMessage] = useState<string | null>(null);

  const refreshSources = async () => {
    setSourceState({ status: 'loading' });
    try {
      const sources = await fetchCaptureSources();
      setSourceState({ status: 'ready', sources });
    } catch {
      setSourceState({
        status: 'error',
        message: 'Could not load capture sources.',
        sources: [],
      });
    }
  };

  const refreshYouTubeStatus = async () => {
    try {
      const status = await fetchYoutubeOAuthStatus();
      setYoutubeStatus(status);
    } catch {
      // Treat an unreachable status endpoint as disconnected instead of
      // leaving the section stuck on "Checking connection...".
      setYoutubeStatus({
        connected: false,
        needsReconnect: false,
        youtubeReadonlyGranted: false,
        hasRefreshToken: false,
        scopes: [],
        expiresAt: null,
        connectedAt: null,
        updatedAt: null,
        lastError: null,
      });
    }
  };

  useEffect(() => {
    refreshSources();
    refreshYouTubeStatus();

    const handleSavedConnection = (event: Event) => {
      const detail = (event as CustomEvent<YoutubeOAuthStatus>).detail;
      if (detail) {
        setYoutubeStatus(detail);
        setYoutubeMessage('YouTube is connected. Add a playlist to start capturing videos.');
      } else {
        refreshYouTubeStatus();
      }
    };

    window.addEventListener(YOUTUBE_CONNECTION_SAVED_EVENT, handleSavedConnection);
    return () => {
      window.removeEventListener(YOUTUBE_CONNECTION_SAVED_EVENT, handleSavedConnection);
    };
  }, []);

  const sources = sourceState.status === 'loading' ? [] : sourceState.sources;

  const handleCreate = async () => {
    const trimmedUrl = playlistUrl.trim();
    if (!trimmedUrl) return;

    setCreating(true);
    setSyncMessage(null);
    const source = await createCaptureSource(trimmedUrl, sourceTitle.trim());
    setCreating(false);
    if (source !== null) {
      setPlaylistUrl('');
      setSyncMessage('Playlist saved.');
      await refreshSources();
      return;
    }

    setSourceState({
      status: 'error',
      message: 'Could not save that playlist. Check the URL and try again.',
      sources,
    });
  };

  const handleConnectYouTube = async () => {
    if (!onConnectYouTube) {
      setYoutubeMessage('Google sign-in is not available right now.');
      return;
    }

    setConnectingYouTube(true);
    setYoutubeMessage(null);
    const result = await onConnectYouTube();
    setConnectingYouTube(false);
    if (result.error) {
      setYoutubeMessage(result.error.message || 'Could not start YouTube connection.');
    }
  };

  const handleDisconnectYouTube = async () => {
    setDisconnectingYouTube(true);
    setYoutubeMessage(null);
    const status = await disconnectYoutubeOAuth();
    setYoutubeStatus(status);
    setDisconnectingYouTube(false);
    setYoutubeMessage('YouTube connection removed.');
  };

  const handleSync = async (source: CaptureSource) => {
    setSyncingSourceId(source.id);
    setSyncMessage(null);
    const preview = await syncCaptureSource(source.id, 0);
    if (preview !== null) {
      const pendingCount = preview.queueCandidateCount ?? preview.newItemCount;
      if (pendingCount <= 0) {
        setSyncingSourceId(null);
        setSyncMessage('Sync is up to date. No new videos are waiting to import.');
        await refreshSources();
        return;
      }

      setSyncingSourceId(null);
      setPendingSync({ source, pendingCount });
      await refreshSources();
      return;
    }

    setSyncingSourceId(null);
    setSourceState({
      status: 'error',
      message: 'Could not sync that playlist right now.',
      sources,
    });
  };

  const handleConfirmSync = async () => {
    if (!pendingSync) return;
    const { source, pendingCount } = pendingSync;
    setConfirmingSync(true);
    setSyncingSourceId(source.id);
    setSyncMessage(null);
    const result = await syncCaptureSource(source.id, pendingCount);
    setConfirmingSync(false);
    setSyncingSourceId(null);
    if (result !== null) {
      const queuedCount = result.queuedJobCount;
      const remainingCount = result.remainingQueueCount ?? Math.max(0, pendingCount - queuedCount);
      setPendingSync(null);
      setSyncMessage(
        remainingCount > 0
          ? `Queued ${queuedCount} of ${pendingCount}. ${remainingCount} still waiting to queue.`
          : `Queued ${queuedCount} video${queuedCount === 1 ? '' : 's'}. Watch Imports for progress.`,
      );
      await refreshSources();
      return;
    }

    setSyncMessage(
      'Sync failed before all imports could be queued. Check Imports for any queued job and retry.',
    );
  };

  const handleCancelSync = async () => {
    if (pendingSync) {
      const pendingCount = pendingSync.pendingCount;
      setSyncMessage(
        `Sync found ${pendingCount} video${pendingCount === 1 ? '' : 's'}. No imports queued.`,
      );
      setPendingSync(null);
      await refreshSources();
      return;
    }
  };

  const handleConfirmDisconnectSource = async () => {
    if (!pendingDisconnectSource) return;
    const source = pendingDisconnectSource;
    setDisconnectingSourceId(source.id);
    setSyncMessage(null);
    const deleted = await deleteCaptureSource(source.id);
    setDisconnectingSourceId(null);
    if (!deleted) {
      setSyncMessage('Could not disconnect that playlist. Refresh and try again.');
      return;
    }
    setPendingDisconnectSource(null);
    setSyncMessage('Playlist disconnected. Saved videos remain in your library.');
    await refreshSources();
  };

  return (
    <section className="min-w-0 rounded-xl border border-ink/10 bg-surface p-4">
      <div className="mb-4">
        <h3 className="font-serif text-2xl font-medium text-ink">YouTube capture inbox</h3>
        <p className="mt-1 text-xs leading-5 text-bark">
          Add the playlist you use to save videos for Memexai.
        </p>
      </div>

      <div className="mb-4 rounded-xl bg-mint/40 p-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h4 className="text-sm font-semibold text-ink">YouTube account</h4>
            <p className="mt-2 text-xs font-semibold text-ink">
              {youtubeStatus === null
                ? 'Checking connection...'
                : formatYouTubeConnectionStatus(youtubeStatus)}
            </p>
            {youtubeMessage ? (
              <p className="mt-1 text-xs font-semibold text-leaf-deep">{youtubeMessage}</p>
            ) : null}
            {youtubeStatus?.lastError ? (
              <p className="mt-1 text-xs font-semibold text-rose-deep">{youtubeStatus.lastError}</p>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <button
              type="button"
              onClick={handleConnectYouTube}
              disabled={connectingYouTube}
              className="btn btn-primary min-h-0 px-4 py-2 text-sm"
            >
              {connectingYouTube
                ? 'Connecting...'
                : youtubeStatus?.connected
                  ? 'Reconnect YouTube'
                  : 'Connect YouTube'}
            </button>
            {youtubeStatus?.connected ? (
              <button
                type="button"
                onClick={handleDisconnectYouTube}
                disabled={disconnectingYouTube}
                className="btn btn-secondary min-h-0 px-4 py-2 text-sm"
              >
                {disconnectingYouTube ? 'Removing...' : 'Disconnect'}
              </button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="grid gap-3">
        <label className="block">
          <span className="mb-1 block text-sm font-semibold text-ink">Playlist URL</span>
          <input
            value={playlistUrl}
            onChange={(event) => setPlaylistUrl(event.target.value)}
            className="input w-full px-3 py-2 text-sm"
            placeholder="https://www.youtube.com/playlist?list=..."
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <label className="block">
            <span className="mb-1 block text-sm font-semibold text-ink">Name</span>
            <input
              value={sourceTitle}
              onChange={(event) => setSourceTitle(event.target.value)}
              className="input w-full px-3 py-2 text-sm"
              placeholder="Memexai Inbox"
            />
          </label>
          <button
            type="button"
            onClick={handleCreate}
            disabled={creating || !playlistUrl.trim()}
            className="btn btn-primary mt-auto min-h-0 px-4 py-2 text-sm"
          >
            {creating ? 'Saving...' : 'Add playlist'}
          </button>
        </div>
      </div>

      {syncMessage ? (
        <p className="mt-3 text-xs font-semibold text-leaf-deep">{syncMessage}</p>
      ) : null}
      {sourceState.status === 'error' ? (
        <p className="mt-3 text-xs font-semibold text-rose-deep">{sourceState.message}</p>
      ) : null}

      <div className="mt-4">
        <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h4 className="text-sm font-semibold text-ink">Connected playlists</h4>
            <p className="mt-1 text-xs leading-5 text-bark">
              Detailed playlist and project management lives in Library.
            </p>
          </div>
          {sources.length > 0 ? (
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">
              {sources.length} linked
            </p>
          ) : null}
        </div>
        {sourceState.status === 'loading' ? (
          <p className="text-xs text-bark">Loading capture sources...</p>
        ) : sources.length > 0 ? (
          <div className="space-y-2">
            {sources.map((source) => (
              <div key={source.id} className="min-w-0 overflow-hidden rounded-xl bg-cream p-3">
                <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink">{source.title}</p>
                    <p className="mt-1 text-xs text-muted">{formatCaptureSourceSummary(source)}</p>
                    {source.last_error ? (
                      <p className="mt-1 text-xs font-semibold text-rose-deep">
                        {source.last_error}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
                    <button
                      type="button"
                      onClick={() => handleSync(source)}
                      disabled={
                        syncingSourceId === source.id || disconnectingSourceId === source.id
                      }
                      className="btn btn-secondary min-h-0 px-4 py-2 text-sm"
                    >
                      {syncingSourceId === source.id ? 'Syncing...' : 'Sync'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setPendingDisconnectSource(source)}
                      disabled={disconnectingSourceId === source.id}
                      className="link-quiet min-h-0 text-sm disabled:opacity-50"
                    >
                      {disconnectingSourceId === source.id
                        ? 'Disconnecting'
                        : 'Disconnect playlist'}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs leading-5 text-bark">No connected playlists yet.</p>
        )}
      </div>
      {pendingSync ? (
        <CaptureSyncConfirmModal
          sourceTitle={pendingSync.source.title}
          pendingCount={pendingSync.pendingCount}
          isSubmitting={confirmingSync}
          onCancel={() => void handleCancelSync()}
          onConfirm={() => void handleConfirmSync()}
        />
      ) : null}
      {pendingDisconnectSource ? (
        <CaptureSourceDisconnectModal
          sourceTitle={pendingDisconnectSource.title}
          isSubmitting={disconnectingSourceId === pendingDisconnectSource.id}
          onCancel={() => setPendingDisconnectSource(null)}
          onConfirm={() => void handleConfirmDisconnectSource()}
        />
      ) : null}
    </section>
  );
};

const AgentAccessSection: React.FC = () => {
  const [tokenState, setTokenState] = useState<McpTokenState>({ status: 'loading' });
  const [tokenName, setTokenName] = useState(DEFAULT_MCP_TOKEN_NAME);
  const [allowAgentIngest, setAllowAgentIngest] = useState(false);
  const [allowAgentProjectSetup, setAllowAgentProjectSetup] = useState(false);
  const [allowAgentPlaylistSync, setAllowAgentPlaylistSync] = useState(false);
  const [createdToken, setCreatedToken] = useState<CreatedMcpToken | null>(null);
  const [creating, setCreating] = useState(false);
  const [copied, setCopied] = useState<
    | 'token'
    | 'config'
    | 'envConfig'
    | 'codexConfig'
    | 'firstSteps'
    | 'setupBundle'
    | 'claudeUrl'
    | 'claudePrompt'
    | null
  >(null);

  const refreshTokens = async () => {
    setTokenState({ status: 'loading' });
    try {
      const tokens = await fetchMcpTokens();
      setTokenState({ status: 'ready', tokens });
    } catch {
      setTokenState({
        status: 'error',
        message: 'Could not load agent tokens.',
        tokens: [],
      });
    }
  };

  useEffect(() => {
    refreshTokens();
  }, []);

  const tokens = tokenState.status === 'loading' ? [] : tokenState.tokens;
  const mcpServerUrl = getMcpServerUrl();
  const mcpManifestUrl = getMcpManifestUrl();
  const agentGuideUrl = getAgentGuideUrl();
  const agentFullGuideUrl = getAgentFullGuideUrl();
  const setupBundle =
    createdToken?.setup ??
    buildLocalMcpSetupBundle(
      mcpServerUrl,
      mcpManifestUrl,
      agentGuideUrl,
      agentFullGuideUrl,
      createdToken?.token,
    );
  const claudeConnector =
    setupBundle.claudeCustomConnector ??
    buildLocalMcpSetupBundle(mcpServerUrl, mcpManifestUrl, agentGuideUrl, agentFullGuideUrl)
      .claudeCustomConnector;
  const envConfigSnippet = setupBundle.hermesConfig;
  const codexConfigSnippet =
    setupBundle.codexConfig ??
    [
      '[mcp_servers.memexai]',
      `url = "${setupBundle.mcpEndpoint}"`,
      `bearer_token_env_var = "${setupBundle.tokenEnvironmentVariable}"`,
      'startup_timeout_sec = 20',
      'tool_timeout_sec = 120',
    ].join('\n');
  const agentFirstStepsSnippet = setupBundle.firstSteps
    .map((step, index) => `${index + 1}. ${step}`)
    .join('\n');
  const configSnippet =
    createdToken?.setup?.oneTimeCredential?.hermesConfig ??
    setupBundle.oneTimeCredential?.hermesConfig ??
    '';
  const setupBundleSnippet =
    createdToken !== null ? JSON.stringify(createdToken.setup ?? setupBundle, null, 2) : '';

  const handleCreate = async () => {
    const name = tokenName.trim() || 'Agent token';
    const scopes = ['context:read', 'overlay:write'];
    if (allowAgentIngest) {
      scopes.push('ingest:write');
    }
    if (allowAgentProjectSetup) {
      scopes.push('project:write');
    }
    if (allowAgentPlaylistSync) {
      scopes.push('capture:write');
    }
    setCreating(true);
    setCreatedToken(null);
    const result = await createMcpToken(name, scopes);
    setCreating(false);
    if (result !== null) {
      setCreatedToken(result);
      setTokenName(name);
      await refreshTokens();
      return;
    }
    setTokenState({
      status: 'error',
      message: 'Could not create an agent token.',
      tokens,
    });
  };

  const handleRevoke = async (tokenId: string) => {
    const success = await revokeMcpToken(tokenId);
    if (success) {
      await refreshTokens();
      return;
    }
    setTokenState({
      status: 'error',
      message: 'Could not revoke that token.',
      tokens,
    });
  };

  const copyText = async (
    kind:
      | 'token'
      | 'config'
      | 'envConfig'
      | 'codexConfig'
      | 'firstSteps'
      | 'setupBundle'
      | 'claudeUrl'
      | 'claudePrompt',
    value: string,
  ) => {
    if (!navigator.clipboard) return;
    await navigator.clipboard.writeText(value);
    setCopied(kind);
    window.setTimeout(() => setCopied(null), 1200);
  };

  return (
    <section className="rounded-xl border border-ink/10 bg-surface p-4">
      <div>
        <h3 className="font-serif text-2xl font-medium text-ink">Agent connection</h3>
        <p className="mt-1 text-xs leading-5 text-bark">
          Connect Claude with OAuth, or create scoped token fallback access for other agents.
        </p>
      </div>
      <div className="mt-4 border-t border-ink/10 pt-4">
        {claudeConnector ? (
          <div className="mb-4 rounded-xl bg-cream p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h4 className="font-serif text-xl font-medium text-ink">Claude custom connector</h4>
                <p className="mt-1 text-xs leading-5 text-bark">
                  Add this remote MCP URL in Claude. Claude opens Google sign-in and the Memexai
                  approval screen.
                </p>
              </div>
              <button
                type="button"
                onClick={() => copyText('claudePrompt', claudeConnector.initialPrompt)}
                className="btn btn-secondary min-h-0 shrink-0 px-3 py-2 text-xs"
              >
                {copied === 'claudePrompt' ? 'Copied' : 'Copy first prompt'}
              </button>
            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto]">
              <label className="block min-w-0">
                <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">
                  MCP URL
                </span>
                <input
                  readOnly
                  value={claudeConnector.url}
                  className="input w-full px-3 py-2 font-mono text-xs"
                />
              </label>
              <button
                type="button"
                onClick={() => copyText('claudeUrl', claudeConnector.url)}
                className="btn btn-secondary mt-auto min-h-0 px-4 py-2 text-sm"
              >
                {copied === 'claudeUrl' ? 'Copied' : 'Copy URL'}
              </button>
            </div>

            <ol className="mt-3 list-decimal space-y-1 pl-5 text-xs leading-5 text-bark">
              {claudeConnector.setupSteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <p className="mt-3 text-xs leading-5 text-bark">{claudeConnector.fallback}</p>
          </div>
        ) : null}

        <div className="mb-3">
          <h4 className="text-sm font-semibold text-ink">Token fallback</h4>
          <p className="mt-1 text-xs leading-5 text-bark">
            Use this for Hermes, Codex, or any MCP client that needs a bearer-token config.
          </p>
        </div>
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => copyText('firstSteps', agentFirstStepsSnippet)}
            className="btn btn-secondary min-h-0 px-3 py-2 text-xs"
          >
            {copied === 'firstSteps' ? 'Copied' : 'Copy setup steps'}
          </button>
          <button
            type="button"
            onClick={() => copyText('envConfig', envConfigSnippet)}
            className="btn btn-secondary min-h-0 px-3 py-2 text-xs"
          >
            {copied === 'envConfig' ? 'Copied' : 'Copy Hermes config'}
          </button>
          <button
            type="button"
            onClick={() => copyText('codexConfig', codexConfigSnippet)}
            className="btn btn-secondary min-h-0 px-3 py-2 text-xs"
          >
            {copied === 'codexConfig' ? 'Copied' : 'Copy Codex config'}
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <label className="block">
            <span className="mb-1 block text-sm font-semibold text-ink">Token name</span>
            <input
              value={tokenName}
              onChange={(event) => setTokenName(event.target.value)}
              className="input w-full px-3 py-2 text-sm"
              placeholder={DEFAULT_MCP_TOKEN_NAME}
            />
          </label>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="btn btn-primary mt-auto min-h-0 px-4 py-2 text-sm"
          >
            {creating ? 'Creating...' : 'Create Token'}
          </button>
        </div>

        <label className="mt-3 flex items-start gap-3 rounded-xl bg-cream p-3">
          <input
            type="checkbox"
            checked={allowAgentIngest}
            onChange={(event) => setAllowAgentIngest(event.target.checked)}
            className="mt-1 h-4 w-4 accent-violet-deep"
          />
          <span>
            <span className="block text-sm font-semibold text-ink">Allow link submissions</span>
            <span className="block text-xs leading-5 text-bark">
              Lets this token queue YouTube links for import. Bulk playlist or channel imports still
              require explicit approval.
            </span>
          </span>
        </label>

        <label className="mt-3 flex items-start gap-3 rounded-xl bg-cream p-3">
          <input
            type="checkbox"
            checked={allowAgentProjectSetup}
            onChange={(event) => setAllowAgentProjectSetup(event.target.checked)}
            className="mt-1 h-4 w-4 accent-violet-deep"
          />
          <span>
            <span className="block text-sm font-semibold text-ink">Allow project setup</span>
            <span className="block text-xs leading-5 text-bark">
              Lets this token create project scopes when you ask the agent to organize a new
              workstream.
            </span>
          </span>
        </label>

        <label className="mt-3 flex items-start gap-3 rounded-xl bg-cream p-3">
          <input
            type="checkbox"
            checked={allowAgentPlaylistSync}
            onChange={(event) => setAllowAgentPlaylistSync(event.target.checked)}
            className="mt-1 h-4 w-4 accent-violet-deep"
          />
          <span>
            <span className="block text-sm font-semibold text-ink">Allow playlist sync</span>
            <span className="block text-xs leading-5 text-bark">
              Lets this token link YouTube playlists to projects and queue confirmed playlist syncs.
            </span>
          </span>
        </label>

        {createdToken !== null ? (
          <div className="mt-4 rounded-xl bg-mint/40 p-4">
            <h4 className="font-serif text-xl font-medium text-ink">Token created</h4>
            <p className="mt-1 text-xs leading-5 text-bark">Save this now. It is shown once.</p>
            <div className="mt-3 flex flex-col gap-2 rounded-xl bg-cream p-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h5 className="text-xs font-semibold text-ink">Setup bundle</h5>
              </div>
              <button
                type="button"
                onClick={() => copyText('setupBundle', setupBundleSnippet)}
                className="btn btn-secondary min-h-0 shrink-0 px-3 py-2 text-xs"
              >
                {copied === 'setupBundle' ? 'Copied' : 'Copy setup bundle'}
              </button>
            </div>
            <div className="mt-3">
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">
                Bearer token
              </label>
              <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
                <input
                  readOnly
                  value={createdToken.token}
                  className="input w-full px-3 py-2 font-mono text-xs"
                />
                <button
                  type="button"
                  onClick={() => copyText('token', createdToken.token)}
                  className="btn btn-secondary min-h-0 px-4 py-2 text-sm"
                >
                  {copied === 'token' ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>
            <div className="mt-3">
              <div className="flex flex-col gap-2 rounded-xl bg-cream p-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h5 className="text-xs font-semibold text-ink">Hermes config with token</h5>
                </div>
                <button
                  type="button"
                  onClick={() => copyText('config', configSnippet)}
                  className="btn btn-secondary min-h-0 shrink-0 px-3 py-2 text-xs"
                >
                  {copied === 'config' ? 'Copied' : 'Copy config'}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        <div className="mt-4">
          <h4 className="mb-2 text-sm font-semibold text-ink">Active tokens</h4>
          {tokenState.status === 'loading' ? (
            <p className="text-xs text-bark">Loading tokens...</p>
          ) : tokens.length > 0 ? (
            <div className="space-y-2">
              {tokens.map((token) => (
                <div
                  key={token.id}
                  className="flex flex-col gap-2 rounded-xl bg-cream p-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
                      {token.name}
                      {token.oauthClientId ? (
                        <span className="rounded-full bg-surface px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-bark">
                          OAuth
                        </span>
                      ) : null}
                    </p>
                    <p className="font-mono text-xs text-muted">
                      {token.tokenPrefix} | {token.scopes.join(', ')}
                    </p>
                    <p className="mt-1 text-xs text-bark">
                      Last used {formatTokenDate(token.lastUsedAt)} &middot; Expires{' '}
                      {formatTokenDate(token.expiresAt)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRevoke(token.id)}
                    className="self-start text-sm font-semibold text-rose-deep underline decoration-2 underline-offset-4 sm:self-center"
                  >
                    Revoke
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs leading-5 text-bark">No active agent tokens yet.</p>
          )}
          {tokenState.status === 'error' ? (
            <p className="mt-2 text-xs font-semibold text-rose-deep">{tokenState.message}</p>
          ) : null}
        </div>
      </div>
    </section>
  );
};

function formatTokenDate(value?: string | null): string {
  if (!value) return 'never';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'unknown';
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatCaptureDate(value?: string | null): string {
  if (!value) return 'never';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'unknown';
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatCaptureSourceSummary(source: CaptureSource): string {
  const status = source.status.replace(/^\w/, (char) => char.toUpperCase());
  const itemCount = source.recentItems?.length ?? 0;
  const parts = [`${status}`, `Last sync ${formatCaptureDate(source.last_synced_at)}`];
  if (itemCount > 0) {
    parts.push(`${itemCount} recent video${itemCount === 1 ? '' : 's'} tracked`);
  }
  return parts.join(' / ');
}
