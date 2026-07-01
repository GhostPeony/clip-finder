import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { approveMcpOAuthAuthorization } from '../services/api';
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
}));

describe('McpAuthorizePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(approveMcpOAuthAuthorization).mockResolvedValue(null);
    window.history.pushState(
      {},
      '',
      '/mcp/authorize?response_type=code&client_id=claude&redirect_uri=http%3A%2F%2Flocalhost%3A31337%2Fcallback&code_challenge=challenge&code_challenge_method=S256&scope=context%3Aread%20overlay%3Awrite&state=state-1',
    );
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
          client_id: 'claude',
          scope: 'context:read overlay:write capture:write',
          state: 'state-1',
        }),
      );
    });
  });

  it('preselects optional scopes already requested by the connector', () => {
    window.history.pushState(
      {},
      '',
      '/mcp/authorize?response_type=code&client_id=claude&redirect_uri=http%3A%2F%2Flocalhost%3A31337%2Fcallback&code_challenge=challenge&scope=context%3Aread%20overlay%3Awrite%20capture%3Awrite',
    );

    render(<McpAuthorizePage />);

    expect(screen.getByLabelText(/playlist sync/i)).toBeChecked();
    expect(screen.getByText('context:read overlay:write capture:write')).toBeInTheDocument();
  });
});
