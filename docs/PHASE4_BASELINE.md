# Phase 4 Baseline (frozen 2026-08-27)

## HEAD
- Branch: `main`
- Commit (pre-Phase-4): `fab0ed6` (UI redesign D-047, UI-01..UI-18 PASS)
- Commits in Phase-4 sequence: `336f907` (M01 baseline inspection)

## Test counts
- Backend pytest: **531/531 PASS** (services/api/tests/)
  - includes security_lab, spend, tickets, webhooks, audit, untrusted_boundary,
    state_machine, stateful_lifecycle, semantic_*, compiler, fusion, gold.
- Phase-3 AI/ML subset (semantic/compiler/fusion/gold): **67/67 PASS**
- Frontend vitest: **14/14 PASS** (apps/web/src/app/smoke.test.tsx + others)
- Playwright E2E redesign-scoped: **9/9 PASS**
  (e2e/smoke.spec.ts 6 + e2e/checkout.spec.ts 3)

## Versions (pre-Phase-4)
- Next.js: 16.3.2 (Turbopack)
- React: 19.2.8
- TypeScript: current
- Python: 3.12 (per `services/api/pyproject.toml`)
- FastAPI / uvicorn: per `services/api` lockfile
- Postgres: 16 (Docker, port 15432)
- Redis: 7 (Docker, port 16379)
- Phase-3 fine-tuned model: frozen per D-046 (`semantic-thresholds-v2`)
- Gold set: 320 cards, sha-bound per D-050
- Untouched OOD set: `data/phase3/eval/untouched_ood/` (per D-049)

## Current DB migration
- Latest alembic head per `services/api/alembic/versions/`
- Test database isolated: `razormesh_test` on the Docker Postgres

## UI state
- Bauhaus system (Outfit + Inter, primary colors, hard borders, hard shadows)
- Pages: `/`, `/buyer`, `/security-lab`, `/audit`, `/merchant`
- All 5 routes prerender as static content (per `pnpm build`)
- Mobile (390×844) + desktop (1440×900) snapshots saved to
  `apps/web/docs/ui-snapshots/`

## Live stack at M05
- API: `uvicorn razormesh_api.api.main:app` on 127.0.0.1:8000
- Web: `pnpm dev` on http://localhost:3000
- DB: Postgres 16 + Redis 7 in Docker

## No Phase-4 protocol code active
This baseline confirms Phase-1/2/3 + UI redesign are green before any
MCP / UCP / AP2 / ACP / A2A code is introduced. The Phase-4 boundary is
clear: nothing in this baseline calls a payment provider, no protocol
adapters, no AI agent harness, no AgentPay-X benchmark.

## Required Phase-4 status preconditions
- M01..M04 PASS (all 4 milestones recorded in PHASE4_STATUS.md)
- Starting commit recorded
- This baseline doc written
- No secrets, no untracked governance drift
