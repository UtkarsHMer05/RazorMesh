# VISUAL_BUDGETS.md — Phase-5 Design/Accessibility Budget (M007)

**Identity preserved:** RazorMesh Bauhaus system (D-047): Outfit display + Inter body, hard
borders, hard shadows, solid blocks (white/yellow/red/blue/dark), yellow CTA, red footer.
**No** generic SaaS/glass/neon redesign. All motion 150–250ms, state-communicating only.

## Typography

- Display (headings, stage names): Outfit 600/700. Hero ≤ 96px @1920, clamp down to 32px.
- Body: Inter 400/500, 16px base; judge-critical text ≥ 16px; presenter mode ≥ 18px.
- Money/amounts: `font-variant-numeric: tabular-nums`, never scientific notation, ₹ formatting
  from backend minor units.
- Line length ≤ 72ch for prose panels.

## Layout budgets

- Canvas widths verified: **1920×1080** (video), **1440×900** (laptop), 1280×800 (fallback).
- Max content width 1200–1440px, centered; usable at 360px without horizontal scroll.
- Pipeline graph (Mission Control): ≤ 1080 tall without scrolling at 1920×1080; vertical flow
  with side evidence panel 360–420px.
- Cards: min touch target 44×44px; borders 3px; shadows from `--rm-shadow-1..3` only on
  interactive elements (no blur).
- Status colors are **never the sole signal**: every PASS/BLOCK/CHALLENGE pairs color + text
  label + shape (badge language from DESIGN.md: "No payment executed" etc.).

## Animation timing budget

- Stage-to-stage packet travel: 600–900ms (video-readable), speed control 0.5×/1×/2×.
- Stage fill: 200ms; result stamp: 250ms; mutation flash: 400ms; probability bar resolve: 500ms.
- All animation off the main thread where trivially possible (CSS transforms/opacity only —
  no layout-thrashing properties).
- Presenter-added waits are UI pacing only and never delay or fake backend results.

## Accessibility

- WCAG AA contrast (Bauhaus tokens already comply: #121212 on #f0f0f0 etc.; verify yellow text
  never on white).
- Full keyboard operability: every control reachable, visible 2px focus ring (`--rm-blue`),
  Enter/Space activation; Esc closes drawers.
- ARIA: live regions (`aria-live="polite"`) for stage progression; `role="status"` for terminal
  outcomes; drawers `role="dialog"` + focus trap; pipeline graph is a labeled list of stages,
  not a canvas-only image.
- Reduced motion: `@media (prefers-reduced-motion: reduce)` → transitions/animations ≤ 1ms,
  states still conveyed by text/shape/position.
- No hidden hover-only affordances; trace badge copy button has visible label.
- Screen reader order = visual order (DOM order enforced; no positive tabindex).

## Reduced-noise rules for judges

- Provider/model branding (Qwen/TokenRouter/DeBERTa file names/hashes) only inside collapsed
  `<details>` "Advanced / Evidence" sections; normal flow uses role names (AI Intent Compiler,
  Shopping Agent, Semantic Trust Check, Model Governance).
- Technical IDs (intent_..., chk_..., tk_...) shown only on demand (copy affordance in advanced
  sections); trace badge is the single visible identifier.
- Every metric carries its source (data-source attribute pattern from landing page).
