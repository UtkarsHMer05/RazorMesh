# VERSION_MANIFEST.md — Live Dependency/Runtime Record

## Rule

Do not fill this file from memory.

Before selecting a meaningful runtime/package version:

1. check the authoritative source;
2. confirm stable/LTS status;
3. confirm architecture compatibility;
4. review current security notices;
5. record the selection;
6. lock it;
7. run compatibility gates.

Newest numeric version is not automatically the correct version.

---

# Runtime manifest

| Component | Selected version | Stable/LTS | Verified date | Official source | Security/compat notes | Reason |
|---|---|---|---|---|---|---|
| Node.js | 22.23.2 (LTS "Jod") | Active LTS | 2026-08-23 | https://nodejs.org/dist/index.json | Release flagged `security: true`; engines `>=20.9` for Next 16 satisfied; arm64 supported via nvm | Newest 22.x LTS line; v20 past EOL (Apr 2026); v24 considered, 22 chosen per human approval and longer field history |
| Python | 3.13.15 pinned in `services/api/.python-version` via uv | Stable, bugfix until 2029-10 | 2026-08-24 | https://www.python.org/downloads/ | 3.14.7 exists; full locked environment and release gates verified on 3.13.15 | Financial code favors the mature 3.13 toolchain; upgrade path to 3.14 remains open |
| PostgreSQL | postgres:18.6-alpine (Docker) | Current stable major (18), patch 18.6 | 2026-08-23 | https://www.postgresql.org/support/versioning/ + Docker Hub library/postgres | 18.6 (2026-08-13) fixes 28 security vulns across supported lines; PG19 is beta — excluded | Latest GA major + current security patch; alpine keeps footprint small on 8 GB M2 |
| Redis | redis:8.8.2-alpine (Docker) | Current stable (8.8.2) | 2026-08-23 | Docker Hub library/redis tags | Used only for nonce claims/locks/coordination; never sole durable truth | Latest stable tag on official image |
| Docker / Compose | Docker 29.7.2, Compose v5.4.0 (installed locally) | Stable Desktop release | 2026-08-23 | `docker --version`, `docker compose version` | Daemon launched on demand during M09 | Already installed; no change required |

# Backend manifest

| Package | Selected version | Verified date | Source | Notes |
|---|---|---|---|---|
| FastAPI | 0.141.1 | 2026-08-23 | PyPI registry metadata (`pip index versions`) | Latest stable |
| Pydantic | 2.13.4 (+ pydantic-settings latest compatible) | 2026-08-23 | PyPI | v2 API |
| SQLAlchemy | 2.0.52 | 2026-08-23 | PyPI | 2.0 series |
| Alembic | 1.19.1 | 2026-08-23 | PyPI | Pairs with SQLAlchemy 2.x |
| uvicorn | 0.52.4 (with `[standard]`) | 2026-08-23 | PyPI | ASGI server |
| psycopg[binary] | 3.3.4 | 2026-08-23 | PyPI | PG driver for SQLAlchemy |
| redis-py | 8.1.0 | 2026-08-23 | PyPI | Client for redis:8.8 server; SET NX EX supported |
| cryptography | 50.0.0 | 2026-08-23 | PyPI | PyCA; Ed25519 signing (decision D-009) |
| rfc8785 | 0.1.4 | 2026-08-23 | PyPI | RFC 8785/JCS canonical JSON implementation (decision D-011); `jcs` 0.2.1 alternative not selected (less complete spec coverage) |
| httpx | 0.28.1 | 2026-08-23 | PyPI | Live HTTP client used by clean-room acceptance |
| pytest | 9.1.1 | 2026-08-23 | PyPI | Test runner |
| pytest-asyncio | 1.4.0 | 2026-08-23 | PyPI | Async tests where needed |
| pytest-cov | latest stable at install (locked in uv.lock) | 2026-08-23 | PyPI | Coverage gate |
| Hypothesis | 6.165.10 | 2026-08-23 | PyPI | Property/stateful testing (decision D-017) |
| Ruff | 0.16.4 | 2026-08-23 | PyPI | Lint + format |
| mypy | 2.3.1 | 2026-08-23 | PyPI | Static type checking; strict-enough config for financial modules |
| pip-audit | 2.10.1 | 2026-08-24 | PyPI JSON API (`https://pypi.org/pypi/pip-audit/json`) | PyPA official dependency auditor; requires-python >=3.10 OK; audits the locked uv venv against the PyPI Advisory database (M48 gate) |
| httpx2 | 2.12.0 | 2026-08-24 | PyPI JSON API (`https://pypi.org/pypi/httpx2/json`) | Stable Starlette 1.6 TestClient dependency; replaces its deprecated legacy-httpx fallback while `httpx` remains for the acceptance client |
| uv | 0.12.5 | 2026-08-23 | astral.sh official installer | Python env/lock management |

# Frontend manifest

| Package | Selected version | Verified date | Source | Notes |
|---|---|---|---|---|
| Next.js | 16.3.2 | 2026-08-23 | npm registry (`npm view next version`) | engines node>=20.9 OK; advisories reviewed at gate M48 |
| React / React-DOM | 19.2.8 | 2026-08-23 | npm registry | Matches Next 16 peer range ^19.0.0 |
| TypeScript | 5.9.3 | 2026-08-23 | npm registry | TS 7.0.2 (native rewrite) exists but is brand-new; 5.9.3 chosen as mature/supported for financial code; TS7 recorded as future path |
| pnpm | 10.18.2 (installed) | 2026-08-23 | `pnpm --version` | Workspace/package manager |
| Vitest | 4.1.11 | 2026-08-23 | npm registry | With vite peer ^7 line auto-resolved |
| @vitejs/plugin-react | 6.1.0 | 2026-08-23 | npm registry | |
| @testing-library/react | 16.3.2 | 2026-08-23 | npm registry | |
| @testing-library/jest-dom | 7.0.1 | 2026-08-23 | npm registry | |
| jsdom | 26.1.0 | 2026-08-24 | npm registry + jsdom release metadata | Pinned compatible Vitest DOM environment; jsdom 30.0.1 introduced an ESM/CJS transitive loader failure with `html-encoding-sniffer`/`@exodus/bytes` in this graph |
| @playwright/test | 1.62.1 | 2026-08-23 | npm registry | Satisfies Next 16 suggested peer ^1.51.1 |
| ESLint | 9.39.5 | 2026-08-24 | npm registry + eslint.org version support | Temporary compatibility exception: v9 reached EOL 2026-08-06, but current Next 16.3.2 plugins declare only through ESLint 9 and crash under 10.9.0 (`contextOrFilename.getFilename is not a function`). Dev-only, production audit clean; upgrade is tracked debt. |
| @razorpay/blade | NOT SELECTED (evaluated 12.111.0) | 2026-08-23 | npm registry + github.com/razorpay/blade | Peer stack pulls styled-components@^5 + framer-motion + RN peers; styled-components v5 + React 19 RSC risk = material Phase-1 complexity → fallback token layer per DESIGN.md §3; decision recorded in DECISIONS.md D-022 |

---

# Version change log

Append changes:

```text
Date:
Milestone:
Component:
Old:
New:
Reason:
Security advisory checked:
Tests run:
Decision reference:
```

| Date | Milestone | Component | Old | New | Reason |
|---|---|---|---|---|---|
| 2026-08-28 | Phase-3 correction (runtime semantic verifier) | torch + transformers (services/api optional `semantic` dependency group) | not installed in API env | torch==2.13.0, transformers==5.15.1 (exact pins) | Production backend is the fine-tuned DeBERTa verifier (D-053); optional group keeps lightweight installs torch-free (fail-closed); exact pins match the versions used to train/revalidate/benchmark the v2 artifact; pip-audit clean at gate time |
| 2026-08-25 | P3-M06 (planned; install at M28+/M31) | transformers | — | 5.15.1 | current stable live-resolved from PyPI; DeBERTa-v3 supported since 4.13+ per model card |
| 2026-08-25 | P3-M06 (planned; install at M19+) | datasets | — | >=5.0.1 | current stable; PYSEC-2026-3716 fixed in 5.0.1 → advisory-driven floor |
| 2026-08-25 | P3-M06 (planned; notebook bundle M31/M32) | accelerate | — | 1.14.0 | current stable, HF Trainer backend |
| 2026-08-25 | P3-M06 (planned; notebook bundle M31/M32) | torch | — | >=2.8 line, exact pin at bundle build | transformers 5.x requires >=2.5; datasets dev uses >=2.8; pip-audit gates the generated lock |
| 2026-08-25 | P3-M06 (planned; optional M47) | onnxruntime | — | 1.29.0 | current stable; py>=3.11 OK |
| 2026-08-25 | P3-M06 | TokenRouter base URL | master prompt: api.tokenrouter.com | documented: api.tokenrouter.io/v1 (R-019) | official docs live-checked; final authority = bootstrap value + M10 probe |
| 2026-08-24 | M48 | pip-audit | — (dev group) | 2.10.1 | TESTING.md §10 dependency-audit gate; latest stable live-resolved from PyPI; advisory DB clean at gate time |
| 2026-08-24 | Phase-1 validation | httpx2 | — (dev group) | 2.12.0 | Starlette 1.6 explicitly prefers httpx2; removes deprecated TestClient fallback warning; stable/Python 3.13 compatible per PyPI |
| 2026-08-24 | Phase-1 validation | Python | unpinned local 3.13.11 | uv-managed 3.13.15 | Align declared and executed runtime; `.python-version` added and full gates rerun |
| 2026-08-24 | Phase-1 validation | jsdom | 30.0.1 | 26.1.0 | Latest release's ESM/CJS transitive graph failed before tests; 26.1.0 is the established compatible stable line and passes Vitest/build/audit |
| 2026-08-24 | Phase-1 validation | ESLint | 9.39.5 | 9.39.5 (temporary exception) | Re-tested 10.9.0; current Next plugins have unmet peers and crash. Keep dev-only v9 until upstream compatibility, with zero production audit findings |
| 2026-08-23 | M14 | ESLint | 10.9.0 | 9.39.5 | eslint-plugin-react@7.37.5 incompatible with ESLint 10; chose newest compatible stable per §11 policy; advisory re-check at M48 |
| 2026-08-23 | M02 | Node.js | v20.20.2 (default) | v22.23.2 LTS default | v20 past EOL Apr 2026; human approved 22 LTS |
| 2026-08-23 | M02 | uv | not installed | 0.12.5 | Governance prefers uv; human approved install |
| Date | Milestone | Component | Old | New | Reason |
|---|---|---|---|---|---|
| 2026-08-24 | P2-M07 | Razorpay client | none | httpx 0.28.1 wrapper (D-030) | official razorpay SDK 2.0.1 declined: Beta classifier, opt-in auto-retry on mutating calls, extra requests dep; httpx already locked, latest stable, 0 advisories |
