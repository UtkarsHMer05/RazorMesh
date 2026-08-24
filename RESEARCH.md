# RESEARCH.md — Evidence and External Research Log

## Research policy

Use this file to record external facts that influence implementation.

Priority:

1. official Razorpay documentation/repositories;
2. official protocol/vendor specifications;
3. official framework/runtime docs;
4. peer-reviewed papers;
5. clearly labeled research preprints;
6. secondary sources only when primary sources are unavailable.

Do not turn a research claim into an implementation claim without actual code/tests.

Every entry should include:

- date checked;
- source title;
- source URL;
- source type;
- key finding;
- project impact;
- confidence/limitations.

---

# R-001 — RazorSense

Date checked: 2026-08-23  
Source: RazorSense — Razorpay Design Language  
URL: https://razorpay.com/razorsense/  
Type: Official Razorpay

Finding:
Razorpay publicly describes RazorSense as a design language for the AI era, emphasizing responsive state, context, emotion, the Razorpay glyph, and deliberate UI states such as cards, buttons, thinking/loading/progress/success.

Impact:
`DESIGN.md` uses these ideas as interaction principles rather than copying undocumented private tokens.

Limitation:
The public page does not establish every exact font/color token. Do not invent them.

---

# R-002 — Razorpay Blade

Date checked: 2026-08-23  
Source: razorpay/blade  
URL: https://github.com/razorpay/blade  
Type: Official Razorpay open-source repository

Finding:
Blade is described as the design system that powers Razorpay, supports React Web/React Native, accessibility, white-labeling and documented API decisions. The package exposes components/tokens/fonts resources.

Impact:
Prefer Blade components/tokens when current package compatibility with the selected Next/React stack is verified.

Limitation:
Live-verify the current package version and framework compatibility before installation.

---

# R-003 — Razorpay brand assets

Date checked: 2026-08-23  
Source: Razorpay Brand Assets  
URL: https://razorpay.com/newsroom/brand-assets/  
Type: Official Razorpay

Finding:
Official logo/assets are subject to Razorpay usage terms.

Impact:
Do not invent/modify official logos or imply endorsement. Prefer RazorMesh identity with Buildathon context.

---

# Research entries to add during Phase 1

The agent should add entries for:

- current Node LTS/stable decision;
- Next.js security/current stable decision;
- React current stable;
- Python runtime;
- FastAPI/Pydantic;
- SQLAlchemy/Alembic;
- PostgreSQL;
- Redis;
- Docker;
- uv;
- Ed25519 library;
- RFC 8785/JCS implementation/library;
- Razorpay Blade installation/current version if used.

---

# R-004 — Node.js current LTS lines

Date checked: 2026-08-23  
Source: Node.js official distribution index  
URL: https://nodejs.org/dist/index.json  
Type: Official runtime metadata

Finding: Latest v22 LTS ("Jod") = 22.23.2, flagged as a security release; latest v24 ("Krypton") = 24.19.0. v20 line past end-of-life (April 2026).

Impact: Select Node v22.23.2 as default runtime (human-approved). Recorded in VERSION_MANIFEST.md.

Confidence: High — primary source.

---

# R-005 — Python release status

Date checked: 2026-08-23  
Source: Python.org downloads  
URL: https://www.python.org/downloads/  
Type: Official

Finding: 3.14.7 is newest stable; 3.13.x in active bugfix phase until 2029-10; 3.12 in security-only phase.

Impact: Use uv-managed Python 3.13 (mature wheel ecosystem for compiled financial/crypto deps). Documented in VERSION_MANIFEST.md.

Confidence: High.

---

# R-006 — PostgreSQL supported versions

Date checked: 2026-08-23  
Source: PostgreSQL global development group  
URL: https://www.postgresql.org/support/versioning/ and https://www.postgresql.org/about/news/postgresql-186-1711-1615-1519-1424-and-19-beta-3-released-3365/  
Type: Official

Finding: Supported majors 18/17/16/15/14; current minors include 18.6, released 2026-08-13 fixing 28 vulnerabilities; PG 19 is beta only.

Impact: Docker image `postgres:18.6-alpine`. PG19 excluded (prerelease).

Confidence: High.

---

# R-007 — Redis stable version

Date checked: 2026-08-23  
Source: Docker Hub official library/redis tags (+ redis/redis unstable release notes cross-check)  
URL: https://hub.docker.com/_/redis  
Type: Official image registry / vendor repo

Finding: Current stable tag family 8.8.2 (`redis:8.8.2-alpine`).

Impact: Selected for docker-compose. Redis remains coordination-only per D-005.

Confidence: High.

---

# R-008 — Razorpay Blade compatibility evaluation

Date checked: 2026-08-23  
Source: npm registry @razorpay/blade metadata  
URL: https://www.npmjs.com/package/@razorpay/blade  
Type: Official package registry for an open-source Razorpay project

Finding: blade@12.111.0 exists with react >=18 peer, but web usage pulls styled-components@^5, framer-motion, react-hot-toast plus React Native peers.

Impact: styled-components@^5 under React 19 + Next 16 App Router/RSC is a material compatibility/complexity risk for Phase 1. Per DESIGN.md §3 escape hatch, Phase 1 uses the documented RazorMesh fallback token layer; Blade re-evaluation deferred to Phase 5 polish. Decision D-022.

Confidence: High on registry facts; judgment call documented as a decision.

---

# R-009 — RFC 8785/JCS implementation choice

Date checked: 2026-08-23  
Source: PyPI registry metadata for `rfc8785` and `jcs` packages  
URL: https://pypi.org/project/rfc8785/  
Type: Package registry (implementation-level)

Finding: `rfc8785` 0.1.4 implements JCS including number serialization rules; `jcs` 0.2.1 relies on host JSON serializer semantics more heavily.

Impact: Select `rfc8785` for canonical authorization hashing (D-011); money stays integer so float edge cases are minimized but the library still enforces spec-compliant output.

Confidence: Medium-high — registry + library docs reviewed at M26 gate with test vectors.

---

# R-010 — Starlette TestClient dependency migration

Date checked: 2026-08-24
Source: PyPI project metadata for `httpx2`
URL: https://pypi.org/pypi/httpx2/json
Type: Authoritative package registry metadata

Finding: `httpx2` 2.12.0 is classified Production/Stable and supports Python
3.13. Starlette 1.6 imports it preferentially and emits a deprecation warning
when falling back to legacy `httpx`.

Impact: Add `httpx2==2.12.0` to the locked development group for TestClient.
Keep `httpx==0.28.1` because the live clean-room acceptance script imports it
directly.

Confidence: High — current installed Starlette source and PyPI metadata agree.

---

# R-011 — jsdom compatibility pin for the Vitest runtime

Date checked: 2026-08-24
Sources: jsdom npm metadata; html-encoding-sniffer package metadata
URLs: https://www.npmjs.com/package/jsdom and https://github.com/jsdom/html-encoding-sniffer/blob/main/package.json
Type: Official package registry / upstream repository

Finding: jsdom 30.0.1 was newly published and its installed dependency graph resolved `html-encoding-sniffer@6` to ESM-only `@exodus/bytes`, while that sniffer still exposes a CommonJS entry. Vitest therefore failed before loading any test. The established jsdom 26.1.0 line avoids that incompatible graph and supports the selected Node runtime.

Impact: Pin `jsdom==26.1.0` exactly for the Phase-1 Vitest environment. The lockfile was regenerated; Vitest, Next build and production dependency audit pass.

Confidence/limitation: High for the reproduced failure and installed graph. This is a compatibility pin, not a claim that every jsdom 30 consumer fails; re-evaluate after the upstream loader graph changes.

---

# R-012 — ESLint 9 temporary compatibility exception

Date checked: 2026-08-24
Sources: ESLint version-support policy and npm release metadata
URLs: https://eslint.org/version-support/ and https://www.npmjs.com/package/eslint
Type: Official project documentation / package registry

Finding: ESLint v9 reached end of life on 2026-08-06 and v10 is current. However, the plugins bundled by `eslint-config-next@16.3.2` declare support only through ESLint 9; an exact 10.9.0 trial produced peer incompatibilities and crashed in `eslint-plugin-react@7.37.5` before linting.

Impact: Retain exact ESLint 9.39.5 as a documented dev-only compatibility exception. Lint passes and `pnpm audit --prod` reports no vulnerabilities. Upgrade when the Next.js plugin stack supports ESLint 10.

Confidence/limitation: High for official lifecycle status and the locally reproduced compatibility failure. ESLint 9 is not described as supported; this debt must remain visible.

---

# Future research topics

Do not implement in Phase 1, but later research will cover:

- Razorpay Orders API;
- Standard Checkout;
- payment signature verification;
- webhook signature/idempotency;
- Razorpay MCP;
- UCP;
- AP2;
- ACP;
- NPCI UAP only from authoritative public specification;
- DeBERTa NLI;
- AgentDojo/CaMeL/PCAS/PayBench-style security evaluation;
- Modal serving;
- Colab fine-tuning.

---

# Open questions

- Is the latest Blade release fully compatible with the selected Next/React versions?
- Which maintained JCS implementation best supports the backend language and cross-language test vectors?
- What exact application-vs-DB controls provide the cleanest append-oriented audit protection in Phase 1?

---

# R-013 — Razorpay Orders API + Standard Checkout (live re-verification)

Date checked: 2026-08-24 (Phase 2 M06)
Sources (official):
- https://razorpay.com/docs/api/orders/
- https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/
Type: Official Razorpay docs

Key findings:
- Orders: POST https://api.razorpay.com/v1/orders, Basic Auth Key_ID:Key_Secret.
  amount = integer subunit; currency = 3 chars; receipt optional max 40 chars;
  notes optional max 15 key-value pairs, each value max 256 chars.
- "An order should be created for every payment"; order_id ties checkout to the
  payment and secures against tampering; payments without order_id cannot be
  captured and are auto-refunded.
- Standard Checkout web: script https://checkout.razorpay.com/v1/checkout.js with
  options key (PUBLIC Key ID only), amount, currency, order_id (mandatory), name,
  handler function (callback_url is only for redirect/WebView flows).
- Success handler returns razorpay_payment_id, razorpay_order_id, razorpay_signature.
- Signature verification is MANDATORY: generated_signature =
  HMAC-SHA256(order_id + "|" + razorpay_payment_id, key_secret) hex digest.
  CRITICAL: use the order_id stored on YOUR server — "Do not use the
  razorpay_order_id returned by Checkout."
- Payment status must reach `captured` before fulfilment; `authorized` alone has
  NOT settled; uncaptured payments auto-refund after a fixed time. Auto-capture is
  a Dashboard setting that works with the Orders API integration.
- Recommended: webhooks for automation + immediate API Fetch when user-facing flow
  needs instant status.

Impact: defines M14 receipt/notes budget, M15 order-create contract, M19 launch
payload, M23 verification formula using server-stored order id (P2-S08), M25
captured-evidence requirement.

Confidence: High (official current docs).

---

# R-014 — Razorpay Webhook validation, dedup and ordering (live re-verification)

Date checked: 2026-08-24 (Phase 2 M06)
Sources (official):
- https://razorpay.com/docs/webhooks/validate-test/
- https://razorpay.com/docs/webhooks/payments/
Type: Official Razorpay docs

Key findings:
- Webhook signature: X-Razorpay-Signature = HMAC-SHA256 over the RAW webhook
  request body keyed by the webhook secret. "Do not parse or cast the webhook
  request body" before verifying. If secret rotated, old events retry under old
  secret.
- Dedup: x-razorpay-event-id header is unique per event; duplicates are expected;
  check whether an event id was already processed.
- Ordering NOT guaranteed: authorized→captured order "may not be followed at all
  times"; systems must handle arbitrary delivery order.
- payment.failed followed by payment.captured for the SAME transaction is
  explicitly documented as EXPECTED behaviour (late authorization; UPI TPAP
  in-app retries). Therefore failed must not be modeled as unrecoverable terminal.
- Webhook payloads are SNAPSHOTS: a payment.authorized payload may describe an
  entity whose real state already advanced to captured.
- payment.captured and order.paid both fire when the payment associated with an
  order is captured ("Once a payment is captured, the order is marked paid") →
  one capture produces two events; business effect must be exactly-once.
- payment.failed is not triggered when a payment fails during initial authorisation.
- Localhost webhook testing requires a public URL; common tunnels (ngrok.io,
  loca.lt, requestbin, webhook.site, etc.) are blacklisted; zrok is recommended.
  Test-mode webhook setup/edit/delete prompts for OTP 754081.

Impact: defines M31 raw-body endpoint, M32 verification tests, M33 durable event
inbox keyed by provider event id, M34 ordering permutations, M26/M29 reducer rules
(failed→captured reconciliation), M35 tunnel choice, M36 gate instructions.

Confidence: High (official current docs).

---

# R-015 — razorpay Python SDK version decision input

Date checked: 2026-08-24 (Phase 2 M06/M07 input)
Source: PyPI JSON API https://pypi.org/pypi/razorpay/json + github.com/razorpay/razorpay-python
Type: Official vendor package registry

Key findings:
- Latest stable release: 2.0.1 (uploaded 2026-03-09); matches master-prompt snapshot.
- Depends on `requests`; exposes opt-in client.enable_retry(True) retry helper.
- PyPI reports no known vulnerabilities for the release.
- Classification remains "Beta" per trove classifier; MIT license.

Impact: candidate for M07 client decision; blanket automatic retries MUST stay OFF
for mutating calls (master prompt §27; P2-S19). Final decision recorded at M07.

Confidence: High (authoritative registry + repo).
