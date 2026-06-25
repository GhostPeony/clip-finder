import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  ReactNode,
} from 'react';
import { AuthError, Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { isSupabaseAuth } from '../config';
import { saveYoutubeOAuthConnection } from '../services/api';

interface AuthActionResult {
  error: AuthError | null;
}

type ProviderSession = Session & {
  provider_token?: string | null;
  provider_refresh_token?: string | null;
};

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signInWithGoogle: (redirectTo?: string) => Promise<AuthActionResult>;
  connectYouTube: () => Promise<AuthActionResult>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);
const YOUTUBE_OAUTH_PENDING_KEY = 'memexai_youtube_oauth_pending';
export const YOUTUBE_CONNECTION_SAVED_EVENT = 'memexai:youtube-connection-saved';
export const YOUTUBE_READONLY_SCOPE = 'https://www.googleapis.com/auth/youtube.readonly';
export const YOUTUBE_OAUTH_SCOPES = ['openid', 'email', 'profile', YOUTUBE_READONLY_SCOPE];

export function getAuthRedirectUrl() {
  if (typeof window === 'undefined') return undefined;
  return window.location.origin;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const youtubeConnectionSaveInFlight = useRef(false);
  const [user, setUser] = useState<User | null>(
    isSupabaseAuth
      ? null
      : ({
          id: 'local',
          email: 'local@clipfinder.dev',
          app_metadata: {},
          aud: 'authenticated',
          created_at: new Date(0).toISOString(),
          user_metadata: { full_name: 'Local User' },
        } as unknown as User),
  );
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(isSupabaseAuth);

  const persistPendingYouTubeConnection = useCallback(async (activeSession: Session | null) => {
    if (!activeSession || typeof window === 'undefined') return;

    const url = new URL(window.location.href);
    const hasRedirectMarker = url.searchParams.get('youtube') === 'connected';
    const hasPendingMarker =
      window.sessionStorage.getItem(YOUTUBE_OAUTH_PENDING_KEY) === '1' || hasRedirectMarker;
    if (!hasPendingMarker || youtubeConnectionSaveInFlight.current) return;

    const providerSession = activeSession as ProviderSession;
    const accessToken = providerSession.provider_token ?? null;
    const refreshToken = providerSession.provider_refresh_token ?? null;
    if (!accessToken && !refreshToken) return;

    youtubeConnectionSaveInFlight.current = true;
    try {
      const status = await saveYoutubeOAuthConnection({
        access_token: accessToken,
        refresh_token: refreshToken,
        scopes: YOUTUBE_OAUTH_SCOPES,
      });
      if (status !== null) {
        window.sessionStorage.removeItem(YOUTUBE_OAUTH_PENDING_KEY);
        if (hasRedirectMarker) {
          url.searchParams.delete('youtube');
          window.history.replaceState(
            {},
            document.title,
            `${url.pathname}${url.search}${url.hash}`,
          );
        }
        window.dispatchEvent(new CustomEvent(YOUTUBE_CONNECTION_SAVED_EVENT, { detail: status }));
      }
    } finally {
      youtubeConnectionSaveInFlight.current = false;
    }
  }, []);

  useEffect(() => {
    if (!isSupabaseAuth) {
      setLoading(false);
      return;
    }

    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
      void persistPendingYouTubeConnection(session);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
      void persistPendingYouTubeConnection(session);
    });

    return () => subscription.unsubscribe();
  }, [persistPendingYouTubeConnection]);

  const signInWithGoogle = async (redirectTo?: string): Promise<AuthActionResult> => {
    if (!isSupabaseAuth) return { error: null };
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: redirectTo || getAuthRedirectUrl(),
        scopes: 'openid email profile',
      },
    });
    return { error };
  };

  const connectYouTube = async (): Promise<AuthActionResult> => {
    if (!isSupabaseAuth) return { error: null };
    if (typeof window !== 'undefined') {
      window.sessionStorage.setItem(YOUTUBE_OAUTH_PENDING_KEY, '1');
    }

    const redirectBase = getAuthRedirectUrl();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: redirectBase ? `${redirectBase}?youtube=connected` : undefined,
        scopes: YOUTUBE_OAUTH_SCOPES.join(' '),
        queryParams: {
          access_type: 'offline',
          prompt: 'consent',
        },
      },
    });

    if (error && typeof window !== 'undefined') {
      window.sessionStorage.removeItem(YOUTUBE_OAUTH_PENDING_KEY);
    }
    return { error };
  };

  const signOut = async () => {
    if (!isSupabaseAuth) return;
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider
      value={{ user, session, loading, signInWithGoogle, connectYouTube, signOut }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
