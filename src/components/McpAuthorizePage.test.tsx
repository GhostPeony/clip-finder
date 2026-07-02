import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { approveMcpOAuthAuthorization, fetchMcpOAuthClientInfo } from '../services/api';
import { McpAuthorizePage } from './McpAuthorizePage';

const authMocks = vi.hoisted(() => ({
  signInWithGoogle: vi.fn(),
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'user-1', email: 'test@example.com' },
    loading: false,
    signInWithGoogle: authMocks.signInWithGoogle,
  }),
}));

vi.mock('../services/api', () => ({
  approveMcpOAuthAuthorization: vi.fn(),
  fetchMcpOAuthClientInfo: vi.fn(),
}));

const RAW_CLIENT_ID = 'memexai_mcp_rawclientid123';

const authorizeUrl = (scope: string) =>
  `/mcp/authorize?response_type=code&client_id=${RAW_CLIENT_ID}` +
  '&redirect_uri=http%3A%2F%2Flocalhost%3A31337%2Fcallback&code_challenge=challenge' +
  `&code_challenge_method=S256&scope=${encodeURIComponent(scope)}&state=state-1`;

describe('McpAuthorizePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(approveMcpOAuthAuthorization).mockResolvedValue(null);
    vi.mocked(fetchMcpOAuthClientInfo).mockResolvedValue(null);
    window.history.pushState({}, '', authorizeUrl('context:read overlay:write'));
  });

  it('lets users explicitly add playlist sync scope during OAuth approval', async () => {
    render(<McpAuthorizePage />);

    expect(screen.getByText('context:read overlay:write')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/playlist sync/i));
    expect(screen.getByText('context:read overlay:write capture:write')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /approve agent/i }));

    await waitFor(() => {
      expect(approveMcpOAuthAuthorization).toHaveBeenCalledWith(
        expect.objectContaining({
          client_id: RAW_CLIENT_ID,
          scope: 'context:read overlay:write capture:write',
          state: 'state-1',
        }),
      );
    });
  });

  it('keeps requested write scopes unchecked until the user explicitly opts in', async () => {
    window.history.pushState({}, '', authorizeUrl('context:read overlay:write capture:write'));

    render(<McpAuthorizePage />);

    // The requested optional write scope is flagged but never pre-granted.
    expect(screen.getByLabelText(/playlist sync/i)).not.toBeChecked();
    expect(screen.getByText(/requested by agent/i)).toBeInTheDocument();
    expect(screen.getByText('context:read overlay:write')).toBeInTheDocument();
    expect(screen.queryByText('context:read overlay:write capture:write')).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/playlist sync/i));
    expect(screen.getByLabelText(/playlist sync/i)).toBeChecked();
    expect(screen.getByText('context:read overlay:write capture:write')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /approve agent/i }));

    await waitFor(() => {
      expect(approveMcpOAuthAuthorization).toHaveBeenCalledWith(
        expect.objectContaining({
          scope: 'context:read overlay:write capture:write',
        }),
      );
    });
  });

  it('never grants a requested write scope the user left unchecked', async () => {
    window.history.pushState(
      {},
      '',
      authorizeUrl('context:read overlay:write ingest:write capture:write'),
    );

    render(<McpAuthorizePage />);

    fireEvent.click(screen.getByRole('button', { name: /approve agent/i }));

    await waitFor(() => {
      expect(approveMcpOAuthAuthorization).toHaveBeenCalledWith(
        expect.objectContaining({
          scope: 'context:read overlay:write',
        }),
      );
    });
  });

  it('shows the registered client name and redirect host, never the raw client_id', async () => {
    vi.mocked(fetchMcpOAuthClientInfo).mockResolvedValue({
      clientName: 'Claude Desktop',
      redirectHosts: ['localhost:31337'],
    });

    render(<McpAuthorizePage />);

    expect(await screen.findByText(/Claude Desktop wants to use/)).toBeInTheDocument();
    expect(screen.getByText('localhost:31337')).toBeInTheDocument();
    expect(screen.queryByText(new RegExp(RAW_CLIENT_ID))).not.toBeInTheDocument();
    expect(fetchMcpOAuthClientInfo).toHaveBeenCalledWith(RAW_CLIENT_ID);
  });

  it('falls back to a generic agent label when the client is not registered', async () => {
    vi.mocked(fetchMcpOAuthClientInfo).mockResolvedValue(null);

    render(<McpAuthorizePage />);

    expect(await screen.findByText(/Your agent wants to use/)).toBeInTheDocument();
    expect(screen.queryByText(new RegExp(RAW_CLIENT_ID))).not.toBeInTheDocument();
  });
});
