import { createClient } from '@supabase/supabase-js'
import { isSupabaseAuth } from '../config'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (isSupabaseAuth && (!supabaseUrl || !supabaseAnonKey)) {
  console.warn('Supabase environment variables not set. Auth will not work.')
}

export const supabase = createClient(
  supabaseUrl || 'http://localhost:54321',
  supabaseAnonKey || 'local-anon-key'
)
