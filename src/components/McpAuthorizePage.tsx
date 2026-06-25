import React, { useMemo, useState } from 'react';
import { approveMcpOAuthAuthorization, ApproveMcpOAuthRequest } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { PRODUCT_NAME } from '../brand';

export const McpAuthorizePage: React.FC = () => {
  const { user, loading, signInWithGoogle } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const request = useMemo(() => buildApproveRequest(params), [params]);
  const clientLabel = params.get('client_id') || 'your agent';
  const scopeText = request?.scope || 'context:read overlay:write';

  const handleSignIn = async () => {
    setError('');
    const result = await signInWithGoogle(window.location.href);
    if (result.error) setError(result.error.message);
  };

  const handleApprove = async () => {
    if (!request) {
      setError('This authorization link is missing required OAuth fields.');
      return;
    }
    setSubmitting(true);
    setError('');
    const result = await approveMcpOAuthAuthorization(request);
    setSubmitting(false);
    if (!result?.redirectUrl) {
      setError('Could not approve this agent connection.');
      return;
    }
    window.location.assign(result.redirectUrl);
  };

  const handleCancel = () => {
    const redirectUri = params.get('redirect_uri');
    if (!redirectUri) {
      window.location.assign('/');
      return;
    }
    const url = new URL(redirectUri);
    url.searchParams.set('error', 'access_denied');
    const state = params.get('state');
    if (state) url.searchParams.set('state', state);
    window.location.assign(url.toString());
  };

  return (
    <main className="min-h-screen bg-cream px-5 py-12 text-ink">
      <div className="mx-auto flex min-h-[70vh] w-full max-w-2xl items-center">
        <section className="card w-full p-6 shadow-lift">
          <p className="eyebrow mb-2">Agent connection</p>
          <h1 className="font-serif text-4xl font-medium text-ink">Connect {PRODUCT_NAME}</h1>
          <p className="mt-3 text-sm leading-6 text-bark">
            {clientLabel} wants to use {PRODUCT_NAME} over MCP. Approving gives it scoped access to
            your saved video context and personal overlay tools.
          </p>

          <div className="mt-5 rounded-xl bg-cream p-4">
            <h2 className="text-sm font-semibold text-ink">Requested access</h2>
            <p className="mt-1 font-mono text-xs text-bark">{scopeText}</p>
            <p className="mt-3 text-xs leading-5 text-bark">
              Source transcripts and generated video context stay read-only. Personal notes and
              concepts are writable only when the token includes overlay access.
            </p>
          </div>

          {error ? <p className="mt-4 text-sm font-semibold text-rose-deep">{error}</p> : null}

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
            <button
              type="button"
              onClick={handleCancel}
              className="btn btn-secondary min-h-0 px-4 py-2 text-sm"
            >
              Cancel
            </button>
            {loading ? (
              <button disabled className="btn btn-primary min-h-0 px-4 py-2 text-sm">
                Checking sign-in...
              </button>
            ) : user ? (
              <button
                type="button"
                onClick={handleApprove}
                disabled={submitting}
                className="btn btn-primary min-h-0 px-4 py-2 text-sm"
              >
                {submitting ? 'Connecting...' : 'Approve agent'}
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSignIn}
                className="btn btn-primary min-h-0 px-4 py-2 text-sm"
              >
                Sign in to approve
              </button>
            )}
          </div>
        </section>
      </div>
    </main>
  );
};

function buildApproveRequest(params: URLSearchParams): ApproveMcpOAuthRequest | null {
  const responseType = params.get('response_type');
  const clientId = params.get('client_id');
  const redirectUri = params.get('redirect_uri');
  const codeChallenge = params.get('code_challenge');
  if (!responseType || !clientId || !redirectUri || !codeChallenge) return null;

  return {
    response_type: responseType,
    client_id: clientId,
    redirect_uri: redirectUri,
    code_challenge: codeChallenge,
    code_challenge_method: params.get('code_challenge_method') || 'S256',
    scope: params.get('scope') || 'context:read overlay:write',
    state: params.get('state'),
    resource: params.get('resource'),
  };
}

export default McpAuthorizePage;
