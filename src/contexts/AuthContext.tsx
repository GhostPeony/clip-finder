import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { Session, User } from '@supabase/supabase-js'
import { supabase } from '../lib/supabase'
import { isSupabaseAuth } from '../config'

interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  signInWithGoogle: () => Promise<void>
  signInWithGitHub: () => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(
    isSupabaseAuth ? null : ({
      id: 'local',
      email: 'local@searchtube.dev',
      app_metadata: {},
      aud: 'authenticated',
      created_at: new Date(0).toISOString(),
      user_metadata: { full_name: 'Local User' },
    } as unknown as User)
  )
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(isSupabaseAuth)

  useEffect(() => {
    if (!isSupabaseAuth) {
      setLoading(false)
      return
    }

    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        setUser(session?.user ?? null)
        setLoading(false)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  const signInWithGoogle = async () => {
    if (!isSupabaseAuth) return
    await supabase.auth.signInWithOAuth({ provider: 'google' })
  }

  const signInWithGitHub = async () => {
    if (!isSupabaseAuth) return
    await supabase.auth.signInWithOAuth({ provider: 'github' })
  }

  const signOut = async () => {
    if (!isSupabaseAuth) return
    await supabase.auth.signOut()
  }

  return (
    <AuthContext.Provider value={{ user, session, loading, signInWithGoogle, signInWithGitHub, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
