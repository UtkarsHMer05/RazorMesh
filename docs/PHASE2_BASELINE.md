# PHASE2_BASELINE.md — Frozen Phase-2 Starting Point

Date frozen: 2026-08-24 (P2-M05)
Statement: **No Razorpay network interaction of any kind has occurred yet.**
The first permitted real interaction is the M12 read-only auth diagnostic.

## Repository

- Branch `main`, HEAD at freeze: `5186cca` (P2-M03 commit)
- History: Phase-1 50/50 (`debfea4`) → human hardening (`cef5a6f`) → P2-M01/M02/M03
- Working tree clean; nothing pushed; `.env` git-ignored with Test credentials PRESENT

## Verified gates at freeze

| Gate | Result |
|---|---|
| ruff check | clean |
| mypy --strict | 48 files clean |
| pytest (+cov) | 225/225, TOTAL coverage 96% under current flags |
| frontend lint/tsc/vitest/build | clean / clean / 3 passed / OK |
| Playwright chromium E2E | 2/2 |
| make security-check | secret scan 0 · pip-audit clean · pnpm audit clean |
| make benchmark | 14 pairs TP14 FP0 TN14 FN0 P=R=F1=1.0 |
| clean-room acceptance | fresh volume → migrate(3) → seed(50) → live API → scripts/acceptance.py **10/10** |
| security lab (live) | 16/16 families |
| migration head | `d8b412f091c3` (execution integrity constraints) |

## Runtime versions

- macOS 26.5 arm64, Apple M2, 8 GB RAM
- Python: venv-managed 3.13 line (`.python-version` pinned by human hardening commit)
- Node v22.23.2 LTS, pnpm 10.18.2
- Docker 29.7.2 / Compose v5.4.0; postgres:18.6-alpine @127.0.0.1:15432;
  redis:8.8.2-alpine @127.0.0.1:16379 (loopback only)
- Key backend pins (full detail `VERSION_MANIFEST.md`): fastapi 0.141.1,
  pydantic 2.13.4, sqlalchemy 2.0.52, alembic 1.19.1, psycopg[binary] 3.3.4,
  redis-py 8.1.0, cryptography 50.0.0, rfc8785 0.1.4, httpx 0.28.1
- Razorpay SDK: **not yet installed** (decision due at P2-M07)

## Phase-1 performance reference

`docs/PHASE1_PERFORMANCE.json` — decide 0.035 ms, ticket verify 0.196 ms,
happy-path execution ≈31 ms incl. DB+Redis (LOCAL ONLY).

## Known limitations inherited from Phase 1

See `docs/PHASE1_COMPLETION_REPORT.md` §6 (mock-only provider, interface-only
semantic verifier, single-machine perf figures, dev-file signing keys, synthetic
benchmark fixtures).
