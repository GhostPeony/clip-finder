export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        cream: 'var(--peony-cream)',
        petal: 'var(--peony-petal)',
        surface: 'var(--peony-surface)',
        ink: 'var(--peony-ink)',
        bark: 'var(--peony-bark)',
        muted: 'var(--peony-muted)',
        rose: {
          DEFAULT: 'var(--peony-rose)',
          deep: 'var(--peony-rose-deep)',
        },
        teal: {
          DEFAULT: 'var(--peony-teal)',
          deep: 'var(--peony-teal-deep)',
        },
        violet: {
          DEFAULT: 'var(--peony-violet)',
          deep: 'var(--peony-violet-deep)',
        },
        leaf: {
          DEFAULT: 'var(--peony-leaf)',
          deep: 'var(--peony-leaf-deep)',
        },
        mint: 'var(--peony-mint)',
        sun: 'var(--peony-sun)',
        lavender: 'var(--peony-lavender)',
        coral: 'var(--peony-coral)',
        sky: 'var(--peony-sky)',
      },
      boxShadow: {
        soft: 'var(--shadow-soft)',
        lift: 'var(--shadow-lift)',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['Fraunces', 'Georgia', 'ui-serif', 'serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      animation: {
        'fade-in-up': 'fade-in-up 180ms ease-out',
      },
      keyframes: {
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translate(-50%, 8px)' },
          '100%': { opacity: '1', transform: 'translate(-50%, 0)' },
        },
      },
    },
  },
  plugins: [],
};
