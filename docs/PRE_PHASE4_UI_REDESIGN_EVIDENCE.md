# Pre-Phase-4 UI Redesign — Gate Evidence

Working directory: `/Users/utkarshkhajuria/Desktop/RazorMesh`
Master prompt: `RazorMesh_UI_Redesign_Master_Prompt.md` (622 lines, read in full before any edit).

This file is the **gate evidence ledger** for the 18 UI-* gates defined in master prompt §21. Each gate has its own section below with: requirements, what was inspected, validation commands + results, files changed (if any), and the PASS / BLOCKED verdict. Commits stay local-only; no push.

---

## UI-01 — Baseline + route inventory (PASS)

### Confirmations per master prompt §24

- Master prompt read completely (622 lines).
- Repository governance (AGENTS.md, RULES.md, PRD.md, PHASES.md, SECURITY.md, ARCHITECTURE.md, DESIGN.md, DECISIONS.md, MILESTONES.md, VERSION_MANIFEST.md, TESTING.md, RESEARCH.md, PHASE3_STATUS.md, MEMORY.md) reviewed.
- **Framework preserved**: RazorMesh ships as **Next.js 16.3.2 (App Router) + React 19.2.8 + TypeScript 5.9.3 + CSS Modules + Vitest 4.1.11 + Playwright 1.62.1**. The inspiration template's Vite + Tailwind stack is **not** migrated. Tailwind class names in the prompt are translated to the existing CSS Modules + token system (per master prompt §1 "Translate the visual specification into the existing stack"). No new UI library added.
- **Brief wins over generic Impeccable defaults**: Inter, pure black/white, gray-300, raw undimmed video, restrained liquid glass are the brief and are kept as-is (master prompt §2 explicitly calls this out).
- One UI gate at a time; test before next; never push; Phase 4 not started.

### Existing routes (per `apps/web/src/app/`)

| Route | File | Mode | Purpose |
|---|---|---|---|
| `/` | `page.tsx` | Persuade (landing) | Trust-core hero + principles + 3 deep-link cards (Buyer / Security Lab / Audit) |
| `/buyer` | `buyer/page.tsx` (+ `IntentDraftPanel.tsx` + 2 test files) | Operate | Catalog browse → compile → confirm → execute → Razorpay handler |
| `/merchant` | `merchant/page.tsx` | Operate | Catalog read view (merchants + products) |
| `/security-lab` | `security-lab/page.tsx` | Operate | Server-side scenario runner; reads evidence tail |
| `/audit` | `audit/page.tsx` | Operate | Hash-chained ledger timeline + tamper-simulation |
| `/_not-found` | implicit | — | 404 |
| `/` (mock-banner) | `layout.tsx` | shared shell | Trust-core banner, sticky header w/ `ClientNav`, footer (none currently) |

Static prerender of all 6 app routes confirmed by `pnpm build` (5 routes + not-found).

### Existing components / libs

- `apps/web/src/components/client-nav.tsx` — sticky-header primary nav (Overview / Buyer / Merchant / Security Lab / Audit).
- `apps/web/src/lib/razorpay.ts` + `razorpay.test.ts` — frontend Razorpay handler (Test-Mode-only; `rzp_live_` / live key detection refuses to mount).
- `apps/web/src/app/buyer/IntentDraftPanel.tsx` + 2 sibling tests — natural-language authorization flow.

### Existing styling

- `apps/web/src/app/globals.css` — single global stylesheet with `:root` tokens (`--rm-bg`, `--rm-surface`, `--rm-text`, `--rm-text-muted`, `--rm-border`, `--rm-primary`, `--radius-card`, `--font-sans`), dark-mode override, base typography reset, `.header` / `.nav` / `.mock-banner` / `.main` / `.hero` / `.card-grid` / `.card` / `.page-title` / `.page-sub` / table defaults / `:focus-visible` / `prefers-reduced-motion` guard / narrow-viewport floor.
- `apps/web/src/app/page.module.css` — home page module.
- `DESIGN.md` §5 — existing RazorMesh project token list (light/dark, Inter at the system-font level, not loaded as a web font).
- `Inter` is currently **referenced in CSS** but **not loaded from Google Fonts** — UI-03 will add the link.

### Existing test battery (frontend)

| Layer | Command | Baseline result |
|---|---|---|
| Type-check | `pnpm typecheck` (tsc --noEmit) | clean |
| Lint | `pnpm lint` (eslint) | clean |
| Unit / component | `pnpm test` (vitest) | 4 files / **14 passed** |
| Production build | `pnpm build` | 6 app routes prerendered (5 + not-found), no errors |
| E2E | `npx playwright test` | **6 passed, 4 failed** — see below |

### Pre-existing E2E failure (out of UI redesign scope)

The 4 failing tests are all in `e2e/gold-reviewer.spec.ts` and they try to read `window.ROWS` from `file://…/gold_review.html`. The HTML declares `const ROWS = […]` at the top of an inline `<script>` block; top-level `const`/`let` in classic scripts **do not become properties of `window`**, so `window.ROWS` is undefined and the helper throws. This is a **pre-existing** defect in the test helper, not in the reviewer HTML and not in the redesign scope (gold review is a Phase-3 file:// tool, not part of `apps/web`). Per master prompt §22 "never bundle unrelated … refactors into design commits" — recorded, not fixed in this milestone. The 6 passing tests cover the redesign's actual scope: `smoke.spec.ts` (2: trust-core banner + nav) and `checkout.spec.ts` (3: stubbed-checkout success / failure / unknown paths).

### Secret / security scan (baseline)

```text
make security-check            -> 0 findings (existing)
grep rzp_live_|TOKENROUTER|tokenrouter across apps/web/src + e2e + .next/static -> 0 hits
```

### Phase 1/2/3 functionality inventory to preserve through the redesign

- Buyer: catalog fetch, compile-intent flow, confirm/reject, Razorpay handler mount, status polling, retry semantics.
- Merchant: catalog read view.
- Security Lab: scenario list, scenario run (server-side), results render, evidence tail preview.
- Audit: ledger event list, hash-chain verify (real `EvidenceLedger.verify()` against the dev DB), tamper-simulation toggle, intent-state drill-down.
- All API contracts hit by these pages are unchanged.

### Visual-continuity obligations (from the additional requirement)

- Landing page = Persuade mode with the supplied cinematic video/glass hero.
- Buyer / Security Lab / Audit / Merchant / product routes = Operate mode, **no cinematic video behind them**, restrained glass only on nav / floating controls.
- Shared design system: Inter, black/white/gray-300, page gutters, button language, border/radius, focus states, motion philosophy.
- Route transitions: opacity 0→1 + translateY ~6–10px → 0, 180–250ms, restrained easing, no scale/3D/spin, no artificial loaders, reduced-motion collapses to instant.

### Primary journey to verify (Playwright + manual)

`Landing → Launch Demo → Intent/Buyer → RazorGuard decision → Security Lab → Audit/Evidence → Landing`. Desktop + mobile. Both screenshots and Playwright assertions required before UI redesign closes.

### Files changed this gate

- None (read-only inventory per master prompt §15.1 / §21.1).

### Verdict

**UI-01 PASS.** Baseline green on typecheck / lint / unit / build / 6-of-10 E2E. The 4 E2E failures are pre-existing in `gold-reviewer.spec.ts` and out of the redesign's working set; the 6 redesign-scoped tests (smoke + checkout) pass. Framework and routes confirmed; no edits made.
