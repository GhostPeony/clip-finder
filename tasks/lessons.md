# Lessons

- Production fork scope is allowed to diverge from the open-source SearchTube defaults. Do not spend effort preserving local/no-auth UX unless it directly helps hosted development or testing.
- For Ghost Peony design work, the design system lives at `C:\Users\Cade\.claude\DESIGN_SYSTEM.md`, not the Codex path. Read that before UI work and apply Botanical Brutalism: warm botanical palette, serif brand type, monospace labels, honest borders, offset shadows, and press-in interactions.
- Do not put a nav item on a product landing page that links to the same product domain. Use meaningful on-page anchors or actions instead.
- Embed Moments landing-page art should be minimal and architectural, not busy faux-product art. Aim for famous-modern-minimalist restraint paired with golden-era brutalist architecture: negative space, one strong form, quiet film/transcript references, and no cheesy demo-card illustration.
- Do not use decorative section badges as a default pattern. Remove boxed eyebrow labels like "Hosted transcript search," "Workflow," and "Use cases" unless they carry functional state or navigation meaning.
- The landing-page chunking visual should be simplified and striking, closer to a Japanese anime production frame than an explanatory graph. Avoid dense bead fields, fake UI diagrams, and abstract copy like "searchable matter."
- When replacing a disliked visual, remove the old wrapper styles too. New markup nested inside stale diagram CSS can make the rendered page look unchanged even when the component changed.
- For premium landing imagery on Embed Moments, prefer generated bitmap art over CSS/SVG-like constructed diagrams when the user asks for a polished product-art feel.
- Do not over-explain product features or auth mechanics in visible UI copy. For Embed Moments beta auth, prefer a confident Google-only sign-in surface over magic-link fallback unless usage shows a real need.
- HARD RULE (DESIGN_SYSTEM.md lines 24, 82): never add boxed eyebrow/badge/pill tags for section names, taglines, or feature labels (e.g. a "Second brain for video" tag above the hero H1). Badges are functional-state only. Use prose/hierarchy. Read DESIGN_SYSTEM.md BEFORE touching any landing markup.
- Never fabricate a "live demo" mockup of the product UI on the landing page. A made-up query/answer/result card that does not match the real dashboard is worse than no demo. Use a real screenshot/GIF of the actual app, or leave the existing art.
