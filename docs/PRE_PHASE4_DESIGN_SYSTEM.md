# RazorMesh Trust — Design System (UI-10)

> Master prompt §10: "After the landing hero is accepted, extract only repeated values/components."

This file is the inventory of the reusable design system shipped in the Pre-Phase-4 UI redesign. It is the single source of truth for tokens and component shapes; UI-18 (handoff) keeps it as a deliverable.

## 1. Tokens (master prompt §10)

All tokens live in `:root` of `apps/web/src/app/globals.css`. No hex is hard-coded outside this file.

| Group | Token | Value | Used by |
|---|---|---|---|
| Surface | `--rm-bg` | `#000000` | `<body>`, all dark-base pages |
| Surface | `--rm-surface` | `#0a0a0a` | cards, panels (operate mode) |
| Surface | `--rm-surface-2` | `#141414` | elevated surfaces |
| Surface | `--rm-surface-glass` | `rgba(0,0,0,0.4)` | liquid-glass background (LOCKED to the canonical class) |
| Type | `--rm-fg` | `#ffffff` | primary text |
| Type | `--rm-muted` | `#d1d5db` (gray-300) | secondary text |
| Type | `--rm-subtle` | `#9ca3af` (gray-400) | tertiary text |
| Divider | `--rm-divider` | `rgba(255,255,255,0.08)` | hairline rules |
| Divider | `--rm-divider-strong` | `rgba(255,255,255,0.16)` | emphasis dividers |
| Status | `--rm-allow` | `#86efac` | ALLOW / PASS / success |
| Status | `--rm-challenge` | `#fcd34d` | CHALLENGE / warning |
| Status | `--rm-block` | `#fca5a5` | BLOCK / danger |
| Status | `--rm-info` | `#93c5fd` | informational |
| Geometry | `--radius-card` | `12px` | cards, panels, hero tag |
| Geometry | `--radius-pill` | `9999px` | primary/secondary buttons |
| Geometry | `--gutter-mobile` | `24px` | horizontal padding (mobile) |
| Geometry | `--gutter-tablet` | `48px` | horizontal padding (md) |
| Geometry | `--gutter-desktop` | `64px` | horizontal padding (lg+) |
| Type stack | `--font-sans` | `'Inter', ui-sans-serif, ...` | global body |
| Type stack | `--font-mono` | `ui-monospace, ...` | architecture, evidence, legal |
| Motion | `--ease-out` | `cubic-bezier(0.22, 0.61, 0.36, 1)` | default |
| Motion | `--ease-in-out` | `cubic-bezier(0.4, 0, 0.2, 1)` | reserved |
| Motion | `--duration-fast` | `150ms` | hover, focus, button state |
| Motion | `--duration-base` | `220ms` | route transition |
| Motion | `--duration-slow` | `480ms` | reserved for emphasis |
| Focus | `--rm-focus` | `#ffffff` (on black) | visible focus ring |

## 2. Components

| Component | File | Used by |
|---|---|---|
| `SiteNav` | `apps/web/src/components/site-nav.tsx` | every page (mounted in `RootLayout`) |
| `HeroVideo` | `apps/web/src/app/_components/hero-video.tsx` | landing hero only |
| `AnimatedHeading` | `apps/web/src/app/_components/animated-heading.tsx` | landing hero (h1) |
| `FadeIn` | `apps/web/src/app/_components/fade-in.tsx` | landing hero (sub, ctas, right tag) |
| `EvidenceMetrics` | `apps/web/src/app/_components/evidence-metrics.tsx` | landing `#proof` section |
| `ArchitectureFlow` | `apps/web/src/app/_components/architecture-flow.tsx` | landing `#architecture` section |

## 3. CSS classes (semantic, not utility)

- `.container` — max-width 1280px, responsive gutters (24/48/64).
- `.site-nav` / `.site-nav__bar` / `.site-nav__brand` / `.site-nav__links` — sticky liquid-glass nav, fixed at top, transparent to mouse on the wrapper.
- `.liquid-glass` — canonical glass material (master prompt §3, exact spec).
- `.btn` / `.btn-primary` / `.btn-secondary` / `.btn-sm` — button system.
- `.card` / `.card-grid` — operate-mode panels.
- `.mock-banner` — test-mode warning bar (operate mode keeps it).
- `.page-title` / `.page-sub` — operate-mode page chrome.
- `.metrics-grid` / `.metric` / `.metric__value` / `.metric__label` / `.metric__detail` — evidence grid.
- `.archflow` / `.archflow__list` / `.archflow__node` / `.archflow__index` / `.archflow__label` / `.archflow__caption` — architecture flow.
- `.seclab-card` / `.seclab-card__row` / `.seclab-card__label` / `.seclab-card__value` / `.seclab-card__value--{allow,challenge,block}` — security-lab preview card.
- `.site-footer` / `.site-footer__inner` / `.site-footer__brand` / `.site-footer__tag` / `.site-footer__nav` / `.site-footer__legal` — landing footer.
- `.hero` / `.hero__content` / `.hero__inner` / `.hero__left` / `.hero__right` / `.hero__heading` / `.hero__sub` / `.hero__ctas` / `.hero__cta` / `.hero__tag` — landing hero (page-scoped in `page.module.css`).
- `.landing-section` / `.eyebrow` / `.section-heading` / `.prose` / `.how-list` / `.how-list__num` — landing below-fold.
- `.route-enter` — global route transition keyframes.
- `.sr-only` — screen-reader-only utility.
- `.divider` — horizontal rule.

## 4. Anti-pattern checklist (master prompt §0 + §11)

- [x] No purple/indigo gradients.
- [x] No glowing blobs.
- [x] No generic bento walls.
- [x] No icon tiles above every heading.
- [x] No excessive pills.
- [x] Glass only on nav + floating emphasis (`.site-nav__bar`, secondary CTA, `.hero__tag`, `.seclab-card`).
- [x] No card-inside-card layouts.
- [x] No fake testimonials, no fake customers, no fake metrics.
- [x] No emoji decoration, no "AI-powered" filler, no hacker-terminal clichés.
- [x] No decorative effects without product meaning.
- [x] No fabricated compliance ("official Razorpay", MCP/UCP/AP2/ACP, etc.).

## 5. Z-stack conventions

- Site nav: `z-index: 50` (fixed, always on top).
- Hero video: `z-index: 0` (decorative, behind content).
- Hero content: `z-index: 10` (relative).
- Liquid-glass pseudo-element: `pointer-events: none` (no interactivity stolen from the parent).

## 6. Motion philosophy

- One `route-enter` keyframe (opacity 0→1, translateY(8px)→0, 220ms, ease-out).
- Hover: 150ms color/background transitions on links + buttons.
- Hero `AnimatedHeading`: per-char translateX + opacity, 500ms, charDelay 30ms, initial 200ms.
- Hero `FadeIn`: opacity 0→1, 1000ms, delays 800 / 1200 / 1400 ms (sub, ctas, right tag).
- Reduced motion: all durations collapse to `0.01ms` via the `prefers-reduced-motion` block in `globals.css` (master prompt §5/§13).

## 7. What this document does NOT contain

- No new framework dependency. No Tailwind. No new UI library. No Vite. No token build tool.
- No `NEXT_PUBLIC_*` secrets (P3-S01).
- No client-side credential surface (P3-S01).
- No new top-level components beyond what is listed in §2. "Do not abstract every div." (master prompt §10).
