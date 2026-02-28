import { useAuth } from '../contexts/AuthContext'

export function LoginPage() {
  const { signInWithGoogle, signInWithGitHub } = useAuth()

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4"
      style={{
        background: 'linear-gradient(135deg, #FAF0EE 0%, #FFF5F3 50%, #F5EDED 100%)',
      }}
    >
      {/* Card */}
      <div
        className="w-full max-w-md p-10"
        style={{
          background: '#FFFFFF',
          border: '2px solid #3D1F1F',
          borderRadius: '12px',
          boxShadow: '4px 4px 0px #3D1F1F',
        }}
      >
        {/* Brand */}
        <div className="text-center mb-8">
          <h1
            className="text-4xl mb-2"
            style={{
              fontFamily: "'Cormorant Garamond', 'Playfair Display', Georgia, serif",
              fontWeight: 300,
              color: '#3D1F1F',
              letterSpacing: '-0.02em',
            }}
          >
            ClipSeek
          </h1>
          <p
            className="text-sm tracking-widest uppercase"
            style={{
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              fontWeight: 600,
              color: '#C25D5D',
              letterSpacing: '0.15em',
            }}
          >
            Find the moment
          </p>
        </div>

        <div className="space-y-3">
          {/* Google OAuth */}
          <button
            onClick={signInWithGoogle}
            className="w-full flex items-center justify-center gap-3 py-3 px-4 transition-all"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontWeight: 600,
              fontSize: '0.85rem',
              letterSpacing: '0.05em',
              background: '#FFFFFF',
              border: '2px solid #3D1F1F',
              borderRadius: '8px',
              boxShadow: '3px 3px 0px #3D1F1F',
              color: '#3D1F1F',
              cursor: 'pointer',
            }}
            onMouseDown={e => {
              const el = e.currentTarget
              el.style.transform = 'translate(2px, 2px)'
              el.style.boxShadow = '1px 1px 0px #3D1F1F'
            }}
            onMouseUp={e => {
              const el = e.currentTarget
              el.style.transform = 'translate(0, 0)'
              el.style.boxShadow = '3px 3px 0px #3D1F1F'
            }}
            onMouseLeave={e => {
              const el = e.currentTarget
              el.style.transform = 'translate(0, 0)'
              el.style.boxShadow = '3px 3px 0px #3D1F1F'
            }}
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Continue with Google
          </button>

          {/* GitHub OAuth */}
          <button
            onClick={signInWithGitHub}
            className="w-full flex items-center justify-center gap-3 py-3 px-4 transition-all"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontWeight: 600,
              fontSize: '0.85rem',
              letterSpacing: '0.05em',
              background: '#3D1F1F',
              border: '2px solid #3D1F1F',
              borderRadius: '8px',
              boxShadow: '3px 3px 0px #8B4545',
              color: '#FAF0EE',
              cursor: 'pointer',
            }}
            onMouseDown={e => {
              const el = e.currentTarget
              el.style.transform = 'translate(2px, 2px)'
              el.style.boxShadow = '1px 1px 0px #8B4545'
            }}
            onMouseUp={e => {
              const el = e.currentTarget
              el.style.transform = 'translate(0, 0)'
              el.style.boxShadow = '3px 3px 0px #8B4545'
            }}
            onMouseLeave={e => {
              const el = e.currentTarget
              el.style.transform = 'translate(0, 0)'
              el.style.boxShadow = '3px 3px 0px #8B4545'
            }}
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
            </svg>
            Continue with GitHub
          </button>
        </div>

        {/* Divider */}
        <div className="mt-8 pt-6" style={{ borderTop: '1px solid #E8D5D5' }}>
          <p className="text-center text-xs" style={{ color: '#8B6B6B', fontFamily: 'Inter, system-ui, sans-serif' }}>
            Search YouTube transcripts with AI-powered semantic search.
            <br />
            Index channels, find exact moments, get timestamp links.
          </p>
        </div>
      </div>

      {/* Footer */}
      <p
        className="mt-6 text-xs"
        style={{
          color: '#8B6B6B',
          fontFamily: "'JetBrains Mono', monospace",
          letterSpacing: '0.1em',
        }}
      >
        Ghost Peony
      </p>
    </div>
  )
}
