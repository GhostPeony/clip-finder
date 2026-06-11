import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { AuthProvider } from './contexts/AuthContext';
import { supabase } from './lib/supabase';

describe('App auth mode', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ status: 'ok', hasApiKey: true }),
      })),
    );
  });

  it('shows the public product page before authentication', async () => {
    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    expect((await screen.findAllByText('Embed Moments')).length).toBeGreaterThan(0);
    expect(document.body.textContent).toContain('embedmoments.com');
    expect(screen.getAllByText('Use cases').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Login').length).toBeGreaterThan(0);
    expect(screen.queryByText('Email link')).not.toBeInTheDocument();
    expect(document.body.textContent).not.toContain('Google sign-in uses identity only');
    expect(screen.queryByText('Continue with GitHub')).not.toBeInTheDocument();
  });

  it('starts Google OAuth with identity-only scopes and the current origin redirect', async () => {
    const signInSpy = vi.spyOn(supabase.auth, 'signInWithOAuth').mockResolvedValue({
      data: { provider: 'google', url: 'https://accounts.google.com' },
      error: null,
    });

    render(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    fireEvent.click((await screen.findAllByText('Login'))[0]);

    await waitFor(() => {
      expect(signInSpy).toHaveBeenCalledWith({
        provider: 'google',
        options: {
          redirectTo: window.location.origin,
          scopes: 'openid email profile',
        },
      });
    });
  });
});
