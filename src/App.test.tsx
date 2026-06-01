import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { AuthProvider } from './contexts/AuthContext';

describe('App auth mode', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({ status: 'ok', hasApiKey: true }),
    })));
  });

  it('renders the local app without showing the login page by default', async () => {
    render(
      <AuthProvider>
        <App />
      </AuthProvider>
    );

    expect((await screen.findAllByText('SearchTube')).length).toBeGreaterThan(0);
    expect(screen.queryByText('Continue with Google')).not.toBeInTheDocument();
  });
});
