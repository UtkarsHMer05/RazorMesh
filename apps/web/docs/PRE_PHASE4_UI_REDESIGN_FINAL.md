# Pre-Phase-4 UI Redesign — Final Evidence

**Status: PASS (UI-01 … UI-18 complete)**
**Approved completion phrase: "Phase-1 local prototype complete." (per AGENTS.md §15)**

This is the final evidence file for the pre-Phase-4 UI redesign. It supersedes
the in-progress notes in `docs/PRE_PHASE4_UI_REDESIGN_EVIDENCE.md`,
`docs/PRE_PHASE4_DESIGN_SYSTEM.md`, and `docs/ui-shape/landing-page.md`.

---

## 1. Surface modes

| Surface | Mode | Aesthetic | Reference |
|---|---|---|---|
| `/` (landing) | **Persuade** | Bauhaus poster — black hero, primary color blocks, geometric shapes | Acme Bauhaus reference |
| `/buyer`     | **Operate** | Bauhaus — cards, hard borders, type-only status pills | Operate pattern |
| `/security-lab` | **Operate** | Bauhaus — same chrome, no cinematic video | Operate pattern |
| `/audit`     | **Operate** | Bauhaus — same chrome, tabular evidence | Operate pattern |
| `/merchant`  | **Operate** | Bauhaus — same chrome, catalog table | Operate pattern |

The video plays **only** on the landing hero. Operate pages are restrained —
shared nav + cards only.

---

## 2. Design tokens (Bauhaus)

| Token | Value | Use |
|---|---|---|
| `--rm-bg` | `#f0f0f0` | Page canvas |
| `--rm-fg` | `#121212` | Stark black, all borders, foreground text |
| `--rm-white` | `#ffffff` | Cards, primary buttons |
| `--rm-red` | `#d02020` | Primary CTA, alert, footer |
| `--rm-blue` | `#1040c0` | Architecture, allow |
| `--rm-yellow` | `#f0c020` | Highlight, CTA strip, eyebrow |
| `--rm-shadow-N` | Npx Npx 0 0 black (no blur) | Hard offset shadows |
| `--rm-font-display` | Outfit 400/700/900 | Headings, labels, numbers |
| `--rm-font-body` | Inter 400/500 | Body text, descriptions |
| `--rm-ease` | `cubic-bezier(0.2, 0.8, 0.2, 1)` | Mechanical motion |
| `--rm-dur` | 200ms | Default transition |

Per AGENTS.md §15, the only completion phrase is **"Phase-1 local prototype
complete."** — no claim of production readiness is made.

---

## 3. Component primitives (all CSS classes global, no Tailwind, no shadcn)

- **`.container`** — `max-width: 1280px; margin: 0 auto;` with 24/40/48px padding.
- **`.site-nav`** — sticky top, white, 4px black bottom border, geometric logo
  (●■▲), nav links with red underline on hover, red "Get Started" CTA.
- **`.hero`** — black, 100svh, video background at 0.55 opacity, geometric
  composition on the right (red square rotating, blue circle floating,
  yellow triangle spinning, white "INTENT. VERIFY. EXECUTE." tag).
- **`.section-heading`** — Bauhaus display heading, kept on one line via
  `word-break: keep-all`; explicit `<span class="line">` blocks in the hero
  prevent mid-word breaks.
- **`.how-tile`** — 5 numbered tiles, alternating red/blue/yellow number chips,
  alternating `±0.6°` tilt.
- **`.arch-step`** — 8-node trust flow, color-blocked per row.
- **`.metric`** — 8 verified metrics with `data-source` attribute pointing to
  the source governance document.
- **`.seclab-card`**, **`.seclab-features`** — live preview + 4 feature cards
  with circle/square/triangle/rotated-square icons.
- **`.cta-strip`** — yellow band with white-on-black CTA.
- **`.site-footer`** — red, three-column layout.
- **`.btn`** — 4 variants (`btn-primary` red, `btn-secondary` white, `btn-blue`,
  `btn-yellow`, `btn-dark`, `btn-outline`). Hover lifts; press translates.
- **`.card`** — 3px black border, hard shadow, hover lift.

All animations honor `prefers-reduced-motion`.

---

## 4. Cross-page navigation (the "everything connects" requirement)

The user explicitly asked that "the security tab like that connects our main
tab it should work like intended without any issues how we ran Phase 2/Phase 3".

Verified by:

1. **End-to-end E2E (`e2e/checkout.spec.ts`)** — 3 stubbed-checkout tests pass
   against the live FastAPI backend. This is the same flow Phase 2/3 used.
2. **Live `GET /catalog/products` → buyer page** — 12 INR products render
   (snapshot `02-buyer-desktop.png`).
3. **Live `GET /security-lab/scenarios` → Security Lab** — 22 registered
   scenarios render (snapshot `03-seclab-desktop.png`).
4. **Live `GET /merchants` + `/catalog/products` → Merchant surface** — 5
   merchants, 50 products (snapshot `05-merchant-desktop.png`).
5. **Internal nav links** — all 6 smoke tests pass (smoke.spec.ts):
   - nav "Get Started" → /buyer
   - hero primary CTA → /buyer
   - hero secondary CTA → /#how (in-viewport)
   - "Open Security Lab" → /security-lab
   - footer "Audit" → /audit
   - trust-core sr-only heading attached
6. **API + Web** — running side-by-side: uvicorn on 127.0.0.1:8000, Next.js on
   3000, Postgres + Redis in Docker.

---

## 5. Validation gates

| Gate | Result |
|---|---|
| `pnpm typecheck` | PASS (mypy + tsc clean) |
| `pnpm lint` (eslint) | PASS |
| `make test-frontend` (vitest) | 14/14 PASS |
| `pnpm build` | PASS, all 6 routes prerendered |
| `make security-check` | PASS (0 secret findings, 0 dep findings) |
| `e2e/smoke.spec.ts` | 6/6 PASS |
| `e2e/checkout.spec.ts` | 3/3 PASS (Phase 2/3-compatible flow) |
| `e2e/gold-reviewer.spec.ts` | 4 pre-existing failures (out of scope, recorded) |
| Visual desktop (1440×900) | 5/5 pages correct |
| Visual mobile (390×844) | 5/5 pages correct |

---

## 6. Final screenshots

`apps/web/docs/ui-snapshots/`:

- `01-landing-desktop.png`, `01-landing-mobile.png`
- `02-buyer-desktop.png`, `02-buyer-mobile.png`
- `03-seclab-desktop.png`, `03-seclab-mobile.png`
- `04-audit-desktop.png`, `04-audit-mobile.png`
- `05-merchant-desktop.png`, `05-merchant-mobile.png`

All snapshots taken against the live dev server (web on :3000, api on :8000)
and the live database (Postgres + Redis in Docker).

---

## 7. Out of scope (carried forward to Phase 4)

- The 4 pre-existing `e2e/gold-reviewer.spec.ts` failures (read
  `window.ROWS` from a `<script>`-scoped `const` — not a UI redesign issue,
  recorded in Phase 2 evidence).
- Pre-existing ruff format drift in `services/api/scripts/*` and
  `services/api/training/phase3/*` — not in UI redesign scope.

---

## 8. Approved completion

> **Phase-1 local prototype complete.**

This UI is a Bauhaus system that connects the landing experience to the
Phase 2/3 buyer / Security Lab / Audit / Merchant surfaces end-to-end. The
next milestone is **Phase 4**, awaiting human approval per
`docs/PHASE3_COMPLETION_REPORT.md`.
