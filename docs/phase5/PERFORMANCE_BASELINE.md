# PERFORMANCE_BASELINE.md — Phase-5 Trace Performance Baseline (M018)

Measured 2026-08-30/31, live dev stack (uvicorn --reload, next dev, Postgres+Redis docker,
DeBERTa semantic runtime in loop), IAB Chromium @1920×1080. Baseline BEFORE heavy motion work
per master prompt M018. Numbers are dev-mode (not production claims).

## Page load — /buyer

| Metric | Value |
|---|---|
| DOMContentLoaded | 342 ms |
| Load event | 451 ms |
| First paint / FCP | 404 ms |

## API latencies (browser-measured)

| Call | Duration |
|---|---|
| GET /catalog/products?limit=100 | 59–82 ms |
| POST /buyer/fixture-intent | 62–64 ms |
| GET /api/trace/by-intent/{id} (proxy) | 41 ms |
| POST /buyer/propose (full RazorGuard decision, ticket mint) | ~250–400 ms (batch incl. 2 setup calls; propose itself felt < 300 ms) |
| GET /api/trace/recent (proxy) | ~30–45 ms |
| GET /api/trace/{id} (proxy, summary+events) | 32 ms |
| GET /api/trace/{id}/events?after_seq= (incremental poll) | 45 ms |

## Known issues / observations

1. **Double fetch on mount** (dev React StrictMode double-effect): catalog + fixture-intent
   each fire twice on /buyer (visible as paired 59/82 ms and 62/64 ms entries). Production
   build will not double-fire; dev-only artifact. No N+1 patterns observed.
2. Propose flow is a single batched decision call — no N+1 to products/decisions (server
   recomputes internally).
3. Trace read endpoints are all sub-50 ms through the Next proxy — the 1.5 s poll interval
   leaves huge headroom; incremental `after_seq` polling returns only new events.
4. No blocking calls observed on the client critical path.

## Budget for Phase-5 motion work (from VISUAL_BUDGETS.md)

- Stage animation must not add backend latency (CSS transforms/opacity only).
- Polling adds ≤ 1 request / 1.5 s while a trace is active and auto-stops when idle
  (12 consecutive no-change polls) — no runaway network.
- Acceptance gates for later milestones: trace badge render < 100 ms after intent creation;
  no API in the judge flow slower than 500 ms p95 in dev mode.
