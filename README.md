# RazorMesh Trust

**Runtime Trust Infrastructure for Agentic Commerce**

> The AI proposes. RazorGuard authorizes. The trusted executor executes.

RazorMesh Trust verifies — immediately before any payment-like side effect — that the
exact transaction still matches the human's confirmed authorization
(**Intent-to-Execution Integrity**).

- Unofficial hackathon prototype built for the Razorpay Buildathon context.
- Phase 1 is **local and credential-free**: a `MockPaymentProvider` stands in for Razorpay.
  No real money, no Razorpay/LLM/cloud credentials, no production claims.

## Documentation map

| File | Purpose |
|---|---|
| `AGENTS.md` | Operating contract for coding agents |
| `RULES.md` | Non-negotiable engineering/security rules |
| `PRD.md` | Product requirements + acceptance criteria |
| `PHASES.md` | Phase roadmap (1–5) |
| `ARCHITECTURE.md` | Flow, modules, data authority, stack |
| `SECURITY.md` | Invariants SEC-001..030 + attack scenarios T1–T18 |
| `DESIGN.md` | UI/design requirements (RazorSense-inspired) |
| `DECISIONS.md` | Append-only decision log (D-001…) |
| `MILESTONES.md` | The gated 50-milestone plan |
| `TESTING.md` | Test gates incl. concurrency C1–C3 |
| `VERSION_MANIFEST.md` | Live-resolved dependency/runtime versions |
| `RESEARCH.md` | External research evidence log |
| `PHASE1_STATUS.md` | Milestone-by-milestone execution evidence |
| `MEMORY.md` | Rolling agent handoff state |
| `docs/PROJECT_CHARTER.md` | Charter: problem, objectives, definition of done |
| `docs/threat-model/` | Phase-1 threat model |

## Repository layout (Phase 1)

```text
apps/web/          Next.js frontend (buyer / merchant / security-lab / audit)
services/api/      FastAPI modular monolith (domain, razor_guard, execution, …)
services/api/tests Backend unit/integration/security/concurrency tests
apps/web/e2e/      Playwright frontend smoke tests
docs/              Benchmark, performance and completion evidence
scripts/           Security, performance and live acceptance utilities
infra/keys/        Generated local development keys (gitignored)
docker-compose.yml PostgreSQL 18 + Redis 8 (loopback-only host bindings)
```

## Status

**Phase-1 local prototype complete** — all 50 milestones PASS with evidence in
`PHASE1_STATUS.md`; see `docs/PHASE1_COMPLETION_REPORT.md`.
All payment flows are **simulated** and labeled as such in the product UI.
