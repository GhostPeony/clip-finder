import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { AuthError, Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { isSupabaseAuth } from '../config';

interface AuthActionResult {
  error: AuthError | null;
}

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signInWithGoogle: () => Promise<AuthActionResult>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function getAuthRedirectUrl() {
  if (typeof window === 'undefined') return undefined;
  return window.location.origin;
}

export function AuthProvider({ children }: { children: ReactNode }) {
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

  useEffect(() => {
    if (!isSupabaseAuth) {
      setLoading(false);
      return;
    }

    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  const signInWithGoogle = async (): Promise<AuthActionResult> => {
    if (!isSupabaseAuth) return { error: null };
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: getAuthRedirectUrl(),
        scopes: 'openid email profile',
      },
    });
    return { error };
  };

  const signOut = async () => {
    if (!isSupabaseAuth) return;
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider value={{ user, session, loading, signInWithGoogle, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
