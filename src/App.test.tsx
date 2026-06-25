import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { AuthProvider, YOUTUBE_READONLY_SCOPE, useAuth } from './contexts/AuthContext';
import { supabase } from './lib/supabase';

function YouTubeConnectHarness() {
  const { connectYouTube } = useAuth();
  return <button onClick={() => void connectYouTube()}>Connect YouTube</button>;
}

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

    expect((await screen.findAllByText('Memexai')).length).toBeGreaterThan(0);
    expect(document.body.textContent).toContain('memexai.xyz');
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

  it('starts Google OAuth with YouTube read-only scope and offline consent when connecting YouTube', async () => {
    const signInSpy = vi.spyOn(supabase.auth, 'signInWithOAuth').mockResolvedValue({
      data: { provider: 'google', url: 'https://accounts.google.com' },
      error: null,
    });

    render(
      <AuthProvider>
        <YouTubeConnectHarness />
      </AuthProvider>,
    );

    fireEvent.click(await screen.findByText('Connect YouTube'));

    await waitFor(() => {
      expect(signInSpy).toHaveBeenCalledWith({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}?youtube=connected`,
          scopes: expect.stringContaining(YOUTUBE_READONLY_SCOPE),
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          },
        },
      });
    });
  });
});
