import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsModal } from './SettingsModal';

const apiMocks = vi.hoisted(() => ({
  createBillingCheckout: vi.fn(),
  createBillingPortal: vi.fn(),
  createCaptureSource: vi.fn(),
  createMcpToken: vi.fn(),
  deleteApiKey: vi.fn(),
  deleteCaptureSource: vi.fn(),
  disconnectYoutubeOAuth: vi.fn(),
  fetchCaptureSources: vi.fn(),
  fetchMcpTokens: vi.fn(),
  fetchUsage: vi.fn(),
  fetchYoutubeOAuthStatus: vi.fn(),
  getAgentFullGuideUrl: vi.fn(),
  getAgentGuideUrl: vi.fn(),
  getMcpManifestUrl: vi.fn(),
  getMcpServerUrl: vi.fn(),
  getStoredLocalApiKey: vi.fn(),
  revokeMcpToken: vi.fn(),
  saveApiKey: vi.fn(),
  saveYoutubeOAuthConnection: vi.fn(),
  syncCaptureSource: vi.fn(),
}));

vi.mock('../services/api', () => ({
  createBillingCheckout: apiMocks.createBillingCheckout,
  createBillingPortal: apiMocks.createBillingPortal,
  createCaptureSource: apiMocks.createCaptureSource,
  createMcpToken: apiMocks.createMcpToken,
  deleteApiKey: apiMocks.deleteApiKey,
  deleteCaptureSource: apiMocks.deleteCaptureSource,
  disconnectYoutubeOAuth: apiMocks.disconnectYoutubeOAuth,
  fetchCaptureSources: apiMocks.fetchCaptureSources,
  fetchMcpTokens: apiMocks.fetchMcpTokens,
  fetchUsage: apiMocks.fetchUsage,
  fetchYoutubeOAuthStatus: apiMocks.fetchYoutubeOAuthStatus,
  getAgentFullGuideUrl: apiMocks.getAgentFullGuideUrl,
  getAgentGuideUrl: apiMocks.getAgentGuideUrl,
  getMcpManifestUrl: apiMocks.getMcpManifestUrl,
  getMcpServerUrl: apiMocks.getMcpServerUrl,
  getStoredLocalApiKey: apiMocks.getStoredLocalApiKey,
  revokeMcpToken: apiMocks.revokeMcpToken,
  saveApiKey: apiMocks.saveApiKey,
  saveYoutubeOAuthConnection: apiMocks.saveYoutubeOAuthConnection,
  syncCaptureSource: apiMocks.syncCaptureSource,
}));

describe('SettingsModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.fetchUsage.mockResolvedValue({
      plan: 'free',
      planKey: 'free',
      billingStatus: 'free',
      searchesUsedToday: 4,
      searchesUsedThisMonth: 4,
      searchLimit: 100,
      searchPeriod: 'month',
      indexesUsedThisMonth: 2,
      indexLimit: 15,
      indexedVideosUsed: 2,
      indexedVideoLimit: 15,
      indexedSecondsUsed: 7200,
      indexedSecondsLimit: 18000,
      monthlyIndexedSecondsUsed: 7200,
      monthlyIndexedSecondsLimit: 18000,
      maxImportVideos: 10,
      maxSearchResults: 5,
      hasOwnKey: true,
      apiKeyMode: 'hybrid',
      hasServerKey: true,
      allowUserKeys: true,
    });
    apiMocks.fetchCaptureSources.mockResolvedValue([]);
    apiMocks.fetchYoutubeOAuthStatus.mockResolvedValue({
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
    apiMocks.fetchMcpTokens.mockResolvedValue([]);
    apiMocks.getAgentGuideUrl.mockReturnValue('https://api.memexai.xyz/llms.txt');
    apiMocks.getAgentFullGuideUrl.mockReturnValue('https://api.memexai.xyz/llms-full.txt');
    apiMocks.getMcpManifestUrl.mockReturnValue('https://api.memexai.xyz/mcp.json');
    apiMocks.getStoredLocalApiKey.mockReturnValue(null);
    apiMocks.getMcpServerUrl.mockReturnValue('https://api.memexai.xyz/mcp');
    apiMocks.saveApiKey.mockResolvedValue(true);
    apiMocks.createBillingCheckout.mockResolvedValue('https://checkout.stripe.com/test');
    apiMocks.createBillingPortal.mockResolvedValue('https://billing.stripe.com/test');
    apiMocks.createCaptureSource.mockResolvedValue(null);
    apiMocks.createMcpToken.mockResolvedValue(null);
    apiMocks.revokeMcpToken.mockResolvedValue(true);
    apiMocks.syncCaptureSource.mockResolvedValue(null);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    apiMocks.disconnectYoutubeOAuth.mockResolvedValue({
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
  });

  const openAgentConnection = async () => {
    fireEvent.click(await screen.findByText('Agent connection'));
  };

  it('shows BYOK model access while keeping hosted storage caps', async () => {
    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys />);

    await waitFor(() => {
      expect(screen.getByText('Searches')).toBeInTheDocument();
    });

    expect(screen.getByText('4 / 100')).toBeInTheDocument();
    expect(screen.getByText('Videos')).toBeInTheDocument();
    expect(screen.getByText('New transcript hours')).toBeInTheDocument();
    expect(screen.getByText('Total library')).toBeInTheDocument();
    expect(screen.getByText('Import size')).toBeInTheDocument();
    expect(
      screen.getByText(
        /Use your Gemini key for model processing where enabled\. Hosted plan limits still apply/,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText('Model access included')).not.toBeInTheDocument();
  });

  it('shows paid plan details before opening checkout', async () => {
    apiMocks.createBillingCheckout.mockRejectedValueOnce(
      new Error('No such customer: cus_old_sandbox'),
    );

    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys />);

    fireEvent.click(await screen.findByRole('button', { name: /^upgrade$/i }));

    expect(screen.getByText('Choose a plan')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /back to settings/i })).toBeInTheDocument();
    expect(screen.queryByText('Gemini API Key')).not.toBeInTheDocument();
    expect(screen.queryByText('YouTube account')).not.toBeInTheDocument();
    expect(screen.getByText('$12/mo')).toBeInTheDocument();
    expect(screen.getByText('$29/mo')).toBeInTheDocument();
    expect(screen.getByText('50 new transcript hours each month')).toBeInTheDocument();
    expect(screen.getByText('Priority queue and 100 videos per import')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^annual$/i }));
    expect(screen.getByText('$288/yr')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /continue with pro/i }));

    await waitFor(() => {
      expect(apiMocks.createBillingCheckout).toHaveBeenCalledWith('memexai_pro_annual_v1');
    });
    expect(await screen.findByText('No such customer: cus_old_sandbox')).toBeInTheDocument();
  });

  it('creates an MCP token and shows copy-first setup actions', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });
    apiMocks.createMcpToken.mockResolvedValue({
      token: 'emt_visible_secret',
      tokenRecord: {
        id: 'token-1',
        name: 'My MCP agent',
        tokenPrefix: 'emt_visible',
        scopes: ['context:read', 'overlay:write'],
      },
      setup: {
        serverName: 'memexai',
        mcpEndpoint: 'https://api.memexai.xyz/mcp',
        manifestUrl: 'https://api.memexai.xyz/mcp.json',
        agentGuideUrl: 'https://api.memexai.xyz/llms.txt',
        fullAgentGuideUrl: 'https://api.memexai.xyz/llms-full.txt',
        claudeCustomConnector: {
          name: 'Memexai',
          url: 'https://api.memexai.xyz/mcp',
          setupSteps: [
            'Open Claude settings, then Customize > Connectors.',
            'Choose Add custom connector and paste the Memexai MCP URL.',
            'Name it Memexai, finish adding it, then click Connect.',
            'Sign in with Google, approve Memexai access, and enable the connector in the chat.',
          ],
          initialPrompt:
            'Use my Memexai connector. Start with get_mcp_session, then list_projects.',
          authMode: 'Remote MCP OAuth through Google sign-in and Memexai approval.',
          fallback: 'If the Claude client cannot complete OAuth, create a scoped MCP token below.',
        },
        tokenEnvironmentVariable: 'MEMEXAI_MCP_TOKEN',
        hermesConfig:
          'mcp_servers:\n  memexai:\n    url: "https://api.memexai.xyz/mcp"\n    headers:\n      Authorization: "Bearer ${MEMEXAI_MCP_TOKEN}"\n    timeout: 180\n    connect_timeout: 30',
        codexConfig:
          '[mcp_servers.memexai]\nurl = "https://api.memexai.xyz/mcp"\nbearer_token_env_var = "MEMEXAI_MCP_TOKEN"\nstartup_timeout_sec = 20\ntool_timeout_sec = 120',
        codexSetupNote: 'Add this to ~/.codex/config.toml. Codex usage stays under your own auth.',
        firstSteps: [
          'Call get_mcp_session to confirm token scopes, owner context, and safe next calls.',
          'Call list_video_library or read context://library before searching.',
          'Use search_video_moments with retrieval_mode=hybrid for timestamp evidence and inspect accessScope/accessReason.',
        ],
        firstCalls: [
          {
            tool: 'get_mcp_session',
            purpose: 'Confirm effective scopes and the MCP token owner context.',
          },
        ],
        accessModel: {
          searchScope: 'current_user_grants',
          globalSearch: 'not_exposed',
          visibilityGrants: ['user_videos', 'user_channels'],
          canonicalStorage: 'Stored once per YouTube video.',
          dedupeBehavior: 'Grant instead of re-embed.',
          agentInstruction: 'Preserve accessScope/accessReason when explaining provenance.',
        },
        oneTimeCredential: {
          bearerToken: 'emt_visible_secret',
          envLine: 'MEMEXAI_MCP_TOKEN=emt_visible_secret',
          hermesConfig:
            'mcp_servers:\n  memexai:\n    url: "https://api.memexai.xyz/mcp"\n    headers:\n      Authorization: "Bearer emt_visible_secret"\n    timeout: 180\n    connect_timeout: 30',
          codexEnvLine: 'MEMEXAI_MCP_TOKEN=emt_visible_secret',
        },
      },
    });
    apiMocks.fetchMcpTokens.mockResolvedValueOnce([]).mockResolvedValueOnce([
      {
        id: 'token-1',
        name: 'My MCP agent',
        tokenPrefix: 'emt_visible',
        scopes: ['context:read', 'overlay:write'],
      },
    ]);

    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys={false} />);

    await openAgentConnection();
    fireEvent.click(await screen.findByRole('button', { name: /create token/i }));

    await waitFor(() => {
      expect(screen.getByText('Token created')).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue('emt_visible_secret')).toBeInTheDocument();
    expect(screen.getByDisplayValue('https://api.memexai.xyz/mcp')).toBeInTheDocument();
    expect(screen.getByText('Claude custom connector')).toBeInTheDocument();
    expect(screen.getByText(/Customize > Connectors/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /copy codex config/i })).toBeInTheDocument();
    expect(screen.getByText('Setup bundle')).toBeInTheDocument();
    expect(screen.getByText('Hermes config with token')).toBeInTheDocument();
    expect(screen.getByText('My MCP agent')).toBeInTheDocument();
    expect(screen.queryByDisplayValue(/ponyo/i)).not.toBeInTheDocument();
    expect(apiMocks.createMcpToken).toHaveBeenCalledWith('My MCP agent', [
      'context:read',
      'overlay:write',
    ]);

    fireEvent.click(screen.getByRole('button', { name: /copy setup bundle/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('current_user_grants'));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('user_videos'));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('codexConfig'));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('emt_visible_secret'));
    });

    fireEvent.click(screen.getByRole('button', { name: /^copy config$/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('connect_timeout: 30'));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('emt_visible_secret'));
    });

    fireEvent.click(screen.getByRole('button', { name: /copy url/i }));
    fireEvent.click(screen.getByRole('button', { name: /copy first prompt/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith('https://api.memexai.xyz/mcp');
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('get_mcp_session'));
    });
  });

  it('keeps public agent docs hidden while still copying setup steps', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys={false} />);
    await openAgentConnection();

    expect(screen.queryByRole('link', { name: 'llms.txt' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'llms-full.txt' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'mcp.json' })).not.toBeInTheDocument();
    expect(screen.queryByText('Agent-readable docs')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /copy setup steps/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('get_mcp_session'));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('collect_repo_context'));
      expect(writeText).toHaveBeenCalledWith(expect.stringContaining('get_repo_context_workflow'));
    });
  });

  it('copies reusable Hermes config that reads the token from the environment', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys={false} />);

    await openAgentConnection();
    expect(screen.getByRole('button', { name: /copy hermes config/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /copy hermes config/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(
        expect.stringContaining('Bearer ${MEMEXAI_MCP_TOKEN}'),
      );
    });
    expect(writeText).toHaveBeenCalledWith(expect.not.stringContaining('emt_visible_secret'));
  });

  it('creates and syncs a YouTube capture source', async () => {
    const captureSource = {
      id: 'capture-1',
      source_type: 'playlist',
      source_url: 'https://www.youtube.com/playlist?list=PLabcdef123456',
      external_id: 'PLabcdef123456',
      title: 'Research inbox',
      status: 'active',
      last_synced_at: '2026-06-22T12:00:00Z',
      recentItems: [
        {
          id: 'item-1',
          youtube_video_id: 'uCKhOmth2ms',
          status: 'queued',
          ingestion_job_id: 'job-1',
          metadata: { title: 'Sierra product harness' },
        },
      ],
    };
    apiMocks.fetchCaptureSources.mockResolvedValue([captureSource]);
    apiMocks.createCaptureSource.mockResolvedValue(captureSource);
    apiMocks.syncCaptureSource
      .mockResolvedValueOnce({
        captureSource,
        discoveredCount: 2,
        newItemCount: 1,
        queueCandidateCount: 2,
        queuedJobCount: 0,
        requestedJobCount: 0,
        remainingQueueCount: 2,
        skippedExistingCount: 1,
        activeJobLimitReached: false,
        queuedJobs: [],
        workflow_instance_id: '12345678-aaaa-bbbb-cccc-123456789abc',
      })
      .mockResolvedValueOnce({
        captureSource,
        discoveredCount: 2,
        newItemCount: 0,
        queueCandidateCount: 2,
        queuedJobCount: 2,
        requestedJobCount: 2,
        remainingQueueCount: 0,
        skippedExistingCount: 2,
        activeJobLimitReached: false,
        queuedJobs: [],
        workflow_instance_id: '12345678-aaaa-bbbb-cccc-123456789abc',
      });

    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys={false} />);

    expect(await screen.findByText('Research inbox')).toBeInTheDocument();
    expect(screen.getByText(/1 recent video tracked/i)).toBeInTheDocument();
    expect(screen.queryByText('Sierra product harness')).not.toBeInTheDocument();
    expect(screen.queryByText(captureSource.source_url)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/playlist url/i), {
      target: { value: 'https://www.youtube.com/playlist?list=PLabcdef123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: /add playlist/i }));

    await waitFor(() => {
      expect(apiMocks.createCaptureSource).toHaveBeenCalledWith(
        'https://www.youtube.com/playlist?list=PLabcdef123456',
        'Memexai Inbox',
      );
    });

    fireEvent.click(screen.getByRole('button', { name: /^sync$/i }));

    expect(await screen.findByRole('dialog', { name: /import 2 videos/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /queue 2 videos/i }));

    await waitFor(() => {
      expect(apiMocks.syncCaptureSource).toHaveBeenNthCalledWith(1, 'capture-1', 0);
      expect(apiMocks.syncCaptureSource).toHaveBeenNthCalledWith(2, 'capture-1', 2);
    });
    expect(window.confirm).not.toHaveBeenCalled();
    expect(await screen.findByText(/queued 2 video/i)).toBeInTheDocument();
    expect(screen.queryByText(/workflow 12345678/i)).not.toBeInTheDocument();
  });

  it('disconnects one playlist capture source without removing YouTube OAuth', async () => {
    const captureSource = {
      id: 'capture-1',
      source_type: 'playlist',
      source_url: 'https://www.youtube.com/playlist?list=PLabcdef123456',
      external_id: 'PLabcdef123456',
      title: 'Research inbox',
      status: 'active',
      last_synced_at: '2026-06-22T12:00:00Z',
      recentItems: [],
    };
    apiMocks.fetchCaptureSources.mockResolvedValue([captureSource]);
    apiMocks.deleteCaptureSource.mockResolvedValue(true);

    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys={false} />);

    expect(await screen.findByText('Research inbox')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /disconnect playlist/i }));
    const dialog = await screen.findByRole('dialog', { name: /disconnect this playlist/i });
    expect(dialog).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('button', { name: /^disconnect playlist$/i }));

    await waitFor(() => {
      expect(apiMocks.deleteCaptureSource).toHaveBeenCalledWith('capture-1');
    });
    expect(apiMocks.disconnectYoutubeOAuth).not.toHaveBeenCalled();
    expect(window.confirm).not.toHaveBeenCalled();
    expect(await screen.findByText(/Playlist disconnected/i)).toBeInTheDocument();
  });

  it('starts YouTube connection from the capture inbox', async () => {
    const onConnectYouTube = vi.fn().mockResolvedValue({ error: null });

    render(
      <SettingsModal
        isOpen
        onClose={() => undefined}
        allowUserKeys={false}
        onConnectYouTube={onConnectYouTube}
      />,
    );

    expect(await screen.findByText('YouTube account')).toBeInTheDocument();
    expect(screen.getByText('Not connected yet.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /connect youtube/i }));

    await waitFor(() => {
      expect(onConnectYouTube).toHaveBeenCalledTimes(1);
    });
  });

  it('shows connected YouTube status and can disconnect', async () => {
    apiMocks.fetchYoutubeOAuthStatus.mockResolvedValue({
      connected: true,
      needsReconnect: false,
      youtubeReadonlyGranted: true,
      hasRefreshToken: true,
      scopes: ['openid', 'https://www.googleapis.com/auth/youtube.readonly'],
      expiresAt: null,
      connectedAt: '2026-06-22T00:00:00Z',
      updatedAt: '2026-06-22T00:00:00Z',
      lastError: null,
    });

    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys={false} />);

    expect(await screen.findByText('Connected with YouTube read access.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /disconnect/i }));

    await waitFor(() => {
      expect(apiMocks.disconnectYoutubeOAuth).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText('YouTube connection removed.')).toBeInTheDocument();
  });

  it('can create an MCP token with YouTube ingestion scope', async () => {
    apiMocks.createMcpToken.mockResolvedValue({
      token: 'emt_visible_secret',
      tokenRecord: {
        id: 'token-1',
        name: 'My MCP agent',
        tokenPrefix: 'emt_visible',
        scopes: ['context:read', 'overlay:write', 'ingest:write'],
      },
    });

    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys={false} />);

    await openAgentConnection();
    fireEvent.click(screen.getByLabelText(/allow link submissions/i));
    fireEvent.click(screen.getByRole('button', { name: /create token/i }));

    await waitFor(() => {
      expect(apiMocks.createMcpToken).toHaveBeenCalledWith('My MCP agent', [
        'context:read',
        'overlay:write',
        'ingest:write',
      ]);
    });
  });

  it('can create an MCP token with agent project and playlist sync scopes', async () => {
    apiMocks.createMcpToken.mockResolvedValue({
      token: 'emt_visible_secret',
      tokenRecord: {
        id: 'token-1',
        name: 'My MCP agent',
        tokenPrefix: 'emt_visible',
        scopes: ['context:read', 'overlay:write', 'project:write', 'capture:write'],
      },
    });

    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys={false} />);

    await openAgentConnection();
    fireEvent.click(screen.getByLabelText(/allow project setup/i));
    fireEvent.click(screen.getByLabelText(/allow playlist sync/i));
    fireEvent.click(screen.getByRole('button', { name: /create token/i }));

    await waitFor(() => {
      expect(apiMocks.createMcpToken).toHaveBeenCalledWith('My MCP agent', [
        'context:read',
        'overlay:write',
        'project:write',
        'capture:write',
      ]);
    });
  });

  it('revokes active MCP tokens', async () => {
    apiMocks.fetchMcpTokens
      .mockResolvedValueOnce([
        {
          id: 'token-1',
          name: 'Claude Desktop',
          tokenPrefix: 'emt_claude',
          scopes: ['context:read', 'overlay:write'],
          lastUsedAt: null,
        },
      ])
      .mockResolvedValueOnce([]);

    render(<SettingsModal isOpen onClose={() => undefined} allowUserKeys={false} />);

    await openAgentConnection();
    expect(await screen.findByText('Claude Desktop')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /revoke/i }));

    await waitFor(() => {
      expect(apiMocks.revokeMcpToken).toHaveBeenCalledWith('token-1');
    });
    await waitFor(() => {
      expect(screen.queryByText('Claude Desktop')).not.toBeInTheDocument();
    });
  });
});
