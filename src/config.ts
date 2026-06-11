export type AuthMode = 'none' | 'supabase';
export type StorageMode = 'local' | 'supabase';

export interface AppConfig {
  storage: StorageMode;
  authMode: AuthMode;
  hasServerKey: boolean;
  apiKeyMode: 'server' | 'byok' | 'hybrid';
  allowUserKeys: boolean;
}

export const AUTH_MODE: AuthMode = import.meta.env.VITE_AUTH_MODE === 'none' ? 'none' : 'supabase';

export const isSupabaseAuth = AUTH_MODE === 'supabase';
