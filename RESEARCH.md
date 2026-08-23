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
