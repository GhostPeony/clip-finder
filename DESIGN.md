# Memexai Design System

Extracted from the live product (memexai.xyz) — `src/index.css` and `tailwind.config.js`
are the code source of truth; this document is the portable spec. Use it to keep any
Memexai-family surface (product UI, landing, docs, companion tools like Capture Deck)
in the same visual voice.

## Identity

Memexai is the **soft bloom** expression of the Ghost Peony botanical family. Where the
global Botanical Brutalism spec uses hard 2px borders and offset shadows, Memexai
softens everything: hairline borders, layered ink-tinted shadows, generous radii, pill
buttons. It should feel like a warm reading room for video knowledge — calm cream
ground, one vivid rose accent, serif display type with real character.

Keep the tension: structure still comes from borders, rhythm, and typography — never
from gradients, glassmorphism, or decorative blobs.

## Typography

| Role                | Face                         | Weights            | Usage                                                |
| ------------------- | ---------------------------- | ------------------ | ---------------------------------------------------- |
| Display / headlines | **Fraunces** (`opsz 9..144`) | 400–600            | h1–h3, hero copy, card titles that carry brand voice |
| UI / body           | **Inter**                    | 400, 500, 600, 700 | everything else; 400–500 body, 600–700 emphasis      |
| Code / labels       | **JetBrains Mono**           | 500                | code, IDs, timestamps, technical values              |

```html
<link
  href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap"
  rel="stylesheet"
/>
```

- Headlines are Fraunces at optical size — big, tight-leading, sentence case with a
  period when making a claim ("Your saved videos are the research corpus.")
- Eyebrow labels: Inter 600, `0.78rem`, uppercase, `letter-spacing: 0.08em`, rose-deep.
- Never introduce a fourth face.

## Color

Background is always warm cream, never white. One vivid accent (rose) owns CTAs and
brand moments; the supporting accents are for functional color-coding only.

### Core

| Token             | Hex       | Role                                           |
| ----------------- | --------- | ---------------------------------------------- |
| `--peony-cream`   | `#fff4df` | page background                                |
| `--peony-surface` | `#fffaf0` | cards, nav, modals, inputs                     |
| `--peony-petal`   | `#ffdfe8` | tinted panels, hero washes                     |
| `--peony-ink`     | `#251b2e` | primary text (warm near-black, violet-leaning) |
| `--peony-bark`    | `#5a3d35` | secondary headings, warm emphasis              |
| `--peony-muted`   | `#7b6374` | secondary text, placeholders                   |

### Accents

| Token                                                                 | Hex                                           | Text-safe deep                  | Role                                             |
| --------------------------------------------------------------------- | --------------------------------------------- | ------------------------------- | ------------------------------------------------ |
| `--peony-rose`                                                        | `#ff6f91`                                     | `--peony-rose-deep` `#b83558`   | THE accent: primary buttons, links, focus, brand |
| `--peony-teal`                                                        | `#22b8a7`                                     | `--peony-teal-deep` `#0a6b60`   | functional coding (e.g. success, agent)          |
| `--peony-violet`                                                      | `#9b7cff`                                     | `--peony-violet-deep` `#6a4fd0` | functional coding (e.g. analysis)                |
| `--peony-leaf`                                                        | `#4dc574`                                     | `--peony-leaf-deep` `#276b3a`   | functional coding (e.g. complete)                |
| `--peony-sun`                                                         | `#ffd95a`                                     | use `--peony-bark` for text     | highlights, `::selection`                        |
| `--peony-mint` / `--peony-lavender` / `--peony-coral` / `--peony-sky` | `#a7f0ba` / `#dccbff` / `#ff9f6e` / `#8bd8ff` | —                               | rare tinted fills only                           |

**Contrast rule:** bright accents are for fills and decoration only. Any accent used
as _text_ on cream/surface must be the `-deep` variant (all deeps ≥ 4.5:1). Selection
is sun on ink: `::selection { background: var(--peony-sun); color: var(--peony-ink) }`.

## Structure

| Token                  | Value                                                                |
| ---------------------- | -------------------------------------------------------------------- |
| Hairline border        | `1px solid rgba(37, 27, 46, 0.1)` (hover: `0.16`)                    |
| Shadow soft            | `0 1px 2px rgba(37,27,46,.05), 0 8px 24px -12px rgba(37,27,46,.14)`  |
| Shadow lift            | `0 2px 4px rgba(37,27,46,.06), 0 16px 40px -16px rgba(37,27,46,.22)` |
| Radius: cards          | `1rem`                                                               |
| Radius: inputs         | `0.75rem`                                                            |
| Radius: buttons, chips | `999px` (pill)                                                       |
| Container max-width    | `1200px`                                                             |

Shadows are always ink-tinted (`rgba(37,27,46,…)`), never gray or black. No hard
offset shadows on Memexai surfaces — that's the sibling brutalist spec, not this one.

## Components

**Card** — surface bg, hairline border, `1rem` radius, shadow-soft. Hover (when
interactive): border to `rgba(37,27,46,.16)`, shadow-lift, `translateY(-2px)`, 0.2s ease.

**Buttons** — pill, Inter 600 `0.9rem`, `min-height 2.75rem`, padding `0.6rem 1.4rem`:

- _Primary:_ rose fill, ink text, rose glow `0 6px 16px -8px rgba(184,53,88,.45)`;
  hover `#ff5c83` + `translateY(-1px)` + deeper glow.
- _Secondary:_ surface fill, hairline border; hover border `0.32` alpha + shadow-soft + lift.
- _Ghost:_ transparent; hover `rgba(37,27,46,.06)` fill.
- Disabled: `opacity 0.55`, `cursor: not-allowed`.

**Chip** — pill, `0.75rem` Inter 600, padding `0.32rem 0.7rem`, tinted fill + deep text:
rose `rgba(255,111,145,.12)`/rose-deep, teal `rgba(34,184,167,.14)`/teal-deep,
violet `rgba(155,124,255,.16)`/violet-deep, leaf `rgba(77,197,116,.16)`/leaf-deep,
sun `rgba(255,217,90,.32)`/bark. Chips are for functional state (status, category,
risk) — never decorative lists of data.

**Input** — surface bg, `1px rgba(37,27,46,.16)` border, `0.75rem` radius; focus:
rose-deep border + `0 0 0 3px rgba(184,53,88,.14)` ring, no outline.

**Eyebrow** — see Typography. Opens sections above a Fraunces headline.

**Quiet link** — ink text, rose underline `1.5px` at `4px` offset; hover deepens the
underline to rose-deep. No color-change links.

**Focus (keyboard)** — `outline: 2px solid var(--peony-rose-deep); outline-offset: 2px;
border-radius: 4px` via `:focus-visible`.

## Motion

- Interactions: `0.15s ease` (color/border), `0.2s ease` (shadow/transform).
- Hover lifts: `-1px` buttons, `-2px` cards. Nothing slides sideways.
- Entrances: `fade-in-up` 180ms ease-out (8px rise).
- Brand loader: bloom pulse (`brand-bloom` / `brand-ring` 1.8s ease-in-out infinite).
- No parallax, no scroll-jacking, no spinners where a bloom will do.

## Voice on the page

- Lead with the user's material: "Your saved videos", "your library" — Memexai is
  infrastructure for _their_ knowledge.
- Feature copy is one plain sentence, no marketing adjectives.
- Scrollbars are styled (6px, ink-alpha thumb, rose-deep hover) — details carry the brand.

## Applying to a new surface

1. Copy the `:root` tokens verbatim (or import from `src/index.css`).
2. Load the three fonts; Fraunces only for display.
3. Build from card/chip/btn/eyebrow recipes above before inventing new components.
4. One rose CTA per view. Supporting accents only as functional coding, always
   deep-variant when used as text.
5. When in doubt: softer, warmer, fewer colors.
