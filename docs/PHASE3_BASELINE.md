# PHASE3_BASELINE.md — Frozen Phase-3 Starting Point

Frozen: 2026-08-25, immediately after P3-M04 PASS, BEFORE any Phase-3 AI/ML
code, dataset work, or dependency addition.

## Git

- Branch `main`, HEAD `d457661` ("P3-M04 PASS: phase-2 provider integrity
  revalidated…"), on top of the Phase-2 completion line ending at `fc0422e`
  (P2-M50 Final Check) + D-037 post-completion audit repairs.
- Working tree clean; nothing pushed (no push authorization).

## Quality state at freeze

| Gate | Result |
|---|---|
| Backend pytest | **375 passed** (stable across repeated runs) |
| ruff format / check | clean (158 files formatted) |
| mypy strict | clean from repo root AND services/api (54 files; caches purged) |
| Hypothesis/stateful subset | 7 passed |
| Focused security keyword subset | 40 passed |
| Frontend lint / tsc / vitest / build | clean / clean / 11 passed / OK |
| Playwright | 5 passed (incl. stubbed-checkout E2E + secret scans) |
| make security-check | PASS — secret scan 0; pip-audit clean; pnpm audit clean |
| Deterministic benchmark | 20 pairs, TP20 TN20 FP0 FN0, **F1 = 1.0** (`docs/PHASE1_BENCHMARK.json`) |
| Migration head | `a93c7d5e21f0` (P2-M13 razorpay correlation + provider_events inbox) |

## Runtime versions (authoritative detail in VERSION_MANIFEST.md)

Python 3.13.15 (uv-pinned); FastAPI 0.141.1; Pydantic 2.13.4; SQLAlchemy
2.0.52; Alembic 1.19.1; httpx 0.28.1; redis-py 8.1.0; pytest 9.1.1 +
Hypothesis 6.165.10; Node 22 LTS; Next 16.3.2; React 19.2.8; TS 5.9.3;
Vitest 4.1.11; Playwright 1.62.1; postgres:18.6-alpine @15432;
redis:8.8.2-alpine @16379.

## Phase-2 references (durable authority this phase builds upon)

- Exactly-once settlement & reservation semantics: D-027/D-028/D-037.
- Callback/webhook verification and precedence: SECURITY.md P2-S07..S16.
- Provider-unknown reconciliation service + ops surface: D-036.
- Real success/failure evidence: docs/PHASE2_M38_*, PHASE2_M39_*,
  PHASE2_M40_EVIDENCE.md.
- Completion report: docs/PHASE2_COMPLETION_REPORT.md.

## Explicit statement

**No Phase-3 AI is active at this baseline.** No TokenRouter client, no Qwen
call, no IntentDraft schema, no AgentPay-IR data, no NLI model, no semantic
policy exists in the codebase yet. The private bootstrap credential has NOT
been read (merge planned at M07; probe at M10; file deletion only after M10
success). RazorMesh still runs exactly the Phase-2 deterministic trust core.

## Known watch items inherited

- ESLint 9 dev-only compatibility exception (see MEMORY).
- razormesh_test database must be provisioned via `make test-db` after any
  `docker compose down -v`.
- zrok share URL is ephemeral; update `.env` RAZORPAY_WEBHOOK_PUBLIC_URL and
  the Dashboard webhook after tunnel restarts if live webhook legs are rerun.
