# RazorMesh Trust

**Zero-Trust Authorization Infrastructure for Agentic Commerce**

> **Protocol validity is not transaction authority.**
>
> **The AI proposes. RazorGuard authorizes. The trusted executor executes.**

`Razorpay Test Mode / local mock only` · `No real money` · `Buildathon prototype`

<!-- Add final Buildathon video link here after upload. -->

[Demo](#4-live-demo--what-the-judge-can-do) · [Architecture](#3-the-30-second-architecture) · [Security](#9-real-protocol-security) · [Model Governance](#10-model-governance) · [Benchmarks](#11-agentpay-x-adversarial-benchmark) · [Run Locally](#15-quick-demo)

---

## 1. Hero — Mission Control, live

[<img src="docs/assets/readme/01-mission-control.webp" alt="RazorMesh Mission Control: the 13-stage trust pipeline with a live BLOCKED trace — protocol and firewall passed, RazorGuard stopped the packet, ticket never issued, provider never contacted" width="960">](docs/assets/readme/01-mission-control.webp)

One authorization lineage, one trace. The checkout may be **revised** by merchant mutations — every revision is revalidated against the **same human authority**. The packet moves only as far as the real evidence says, and never past a BLOCK.

**RazorMesh adds a dedicated intent-to-transaction authorization check immediately before an AI-originated payment reaches the provider** — re-verifying, at execution time, that the exact current transaction still matches the human-confirmed authorization (**Intent-to-Execution Integrity**).

## 2. The problem

An AI agent can submit a transaction that is **schema-valid, authenticated, correctly signed, and replay-safe — and still not what the human authorized.**

```
Human approved            →  ₹4,799 · one-time purchase
Agent / merchant mutation →  ₹4,799 + recurring membership ₹499/month

Protocol validity        →  PASS
Transaction authority    →  BLOCK
```

**Protocol validity is not transaction authority.** RazorMesh adds a dedicated intent-to-transaction re-check immediately before execution — twice, deterministically and semantically, against the human-confirmed authorization.

## 3. The 30-second architecture

```mermaid
flowchart LR
    H[Human authorization] --> A[AI shopping agent]
    A --> M[Merchant offer]
    M --> P[Agent protocol]
    P --> F[Protocol firewall]
    F --> IR[AgentCommerceIR]
    IR --> R[Deterministic RazorGuard]
    IR --> S[Semantic trust]
    R --> X[Conservative fusion]
    S --> X
    X -->|ALLOW| T[ExecutionTicket]
    X -->|BLOCK| W[Ticket NOT ISSUED]
    T --> EX[Trusted executor]
    EX --> RP[Razorpay Test / mock]
    EX --> RC[Reconciliation]
    RP --> AU[Tamper-evident audit]
    RC --> AU
    W --> AU
```

**Protocol validity ≠ transaction authority.** Everything upstream of RazorGuard is evidence, never authority: the AI proposes, deterministic hard rules + a semantic NLI model check the *current* transaction against the confirmed authorization, and only an ALLOW can mint a short-lived, single-use, context-bound **ExecutionTicket** that the trusted executor — and only the trusted executor — redeems, exactly once. Neither the AI nor the protocol layer can issue money authority.

<details>
<summary><b>Why two checks (deterministic + semantic)?</b></summary>

Deterministic RazorGuard reads the structured projection — budgets, quantity, recurring flags, merchant/condition allowlists — and catches every rule it models. The semantic model reads the *commerce evidence text* against the *human authorization text* and catches contradictions no rule encodes (see [Demo C](#demo-c--why-semantic-ai-matters)). Semantic verdicts can only **tighten** a decision — never loosen one.

</details>

## 4. Live demo — what the judge can do

| Surface | Local route | What you can demonstrate |
|---|---|---|
| **Buyer — AI Commerce Mission** | `/buyer` | Type a natural-language mandate → **real AI Intent Compiler** extracts hard constraints → human confirms authority → real shopping-agent search/rank over the catalog → checkout proposal. |
| **Mission Control** | `/mission-control` | The 13-stage pipeline on the live trace; **DEMO PREFLIGHT** readiness probes; authorization-vs-current diff; mutations/revert/execute on the *current* trace; read-only replay. |
| **Merchant Sandbox** | `/merchant` | Mutate a real checkout after authorization (price drift, quantity, merchant swap, hidden membership) and watch the same trace detect drift. |
| **Protocol Playground** | `/protocols` | Real packet mutations through the real firewall + IR + consistency engine; **real UCP RFC 9421/9530 and AP2 ES256 signature verification** (safe → verified; tampered bytes → real verifier FAIL). |
| **Security Lab** | `/security-lab` | Attack demos with per-stage verdicts; **Why semantic AI matters** (real engines end-to-end). |
| **Audit Forensics** | `/audit` | Search by trace/intent/checkout/attempt/order id; this trace's **anchors in the global hash chain**; read-only replay; tamper test. |
| **Model Governance** | `/governance` | Active vs challenger model truth; the **actual rejected v2 checkpoint** running live, shadow-only, in canonical NLI orientation. |

There is no deployed demo — run locally using the [Quick Demo instructions](#15-quick-demo) below.

## 5. Screenshot gallery

All screenshots are the current build with real engine state (click to enlarge).

<table>
<tr>
<td width="50%"><a href="docs/assets/readme/02-buyer-ai-mission.webp">
      <img src="docs/assets/readme/02-buyer-ai-mission.webp"
        alt="Buyer AI Commerce Mission"
        width="480">
    </a><br><b>Buyer — mandate → AI compilation → constraints</b></td>
<td width="50%"><a href="docs/assets/readme/03-merchant-mutation.webp">
      <img src="docs/assets/readme/03-merchant-mutation.webp"
        alt="Merchant mutation diff"
        width="480">
    </a><br><b>Merchant — hidden membership inserted after authorization</b></td>
</tr>
<tr>
<td width="50%"><a href="docs/assets/readme/04-protocol-playground.webp">
      <img src="docs/assets/readme/04-protocol-playground.webp"
        alt="Protocol Playground"
        width="480">
    </a><br><b>Protocol Playground — UCP corrupt-signature → real verifier FAIL</b></td>
<td width="50%"><a href="docs/assets/readme/05-security-semantic-ai.webp">
      <img src="docs/assets/readme/05-security-semantic-ai.webp"
        alt="Security Lab semantic AI demo"
        width="480">
    </a><br><b>Security Lab — Why semantic AI matters</b></td>
</tr>
<tr>
<td width="50%"><a href="docs/assets/readme/06-audit-forensics.webp">
      <img src="docs/assets/readme/06-audit-forensics.webp"
        alt="Audit Forensics"
        width="480">
    </a><br><b>Audit — anchors in the global chain, CHAIN VALID</b></td>
<td width="50%"><a href="docs/assets/readme/07-model-governance.webp">
      <img src="docs/assets/readme/07-model-governance.webp"
        alt="Model Governance"
        width="480">
    </a><br><b>Governance — real v2 challenger in shadow, ignored for authority</b></td>
</tr>
</table>

## 6. How to read this repository

<details>
<summary><b>See why the semantic model is necessary (real engine output)</b></summary>

| Stage | Verdict |
|---|---|
| Structured RazorGuard (real rule engine, pre-issuance evaluation) | **ALLOW** — structured facts carry no violation |
| Semantic trust (active PRE_V2 model) | **BLOCK** — p(contradiction) 0.9998 |
| Conservative fusion (real `fuse` seam) | **BLOCK** |
| ExecutionTicket | **NOT ISSUED** — the issuance stage was never reached |
| Execution attempt | **NOT CREATED** |
| Provider calls | **0** |

The deterministic evaluation alone would have let this transaction proceed to a ticket — exactly the gap the semantic check closes. Durable proof: ticket / attempt / provider-event counts are identical before and after the demo run.

</details>

<details>
<summary><b>See the rejected v2 challenger safety gate</b></summary>

The fine-tuned **AgentPay-IR v2** candidate improved in-distribution macro-F1 (0.737 → 0.975) but **worsened unsafe contradiction→entailment on the security-critical sets**:

| Dataset (frozen, one-shot) | PRE_V2 macro-F1 | v2 macro-F1 | Unsafe C→E (PRE_V2 → v2) |
|---|---|---|---|
| Final test | 0.737 | 0.975 | 43 → 13 |
| Human gold | **0.893** | 0.776 | **2 → 7 (worse)** |
| Fresh OOD | 0.822 | 0.918 | **5 → 6 (worse)** |

A model that lets more gold contradictions reach a provider-call PASS must not ship — whatever its macro-F1. **RazorMesh refused to activate it.**

</details>

<details>
<summary><b>Run the demo preflight before presenting</b></summary>

Open `/mission-control` → **Run demo preflight (+ warm-up compiler)**. Expected: PostgreSQL READY · Redis READY · Payment environment (RAZORPAY TEST MODE / LOCAL MOCK) · AI Intent Compiler READY · Active Semantic Model READY · ExecutionTicket signing keys READY · Protocol crypto READY · Audit chain READY · V2 Challenger READY *or honestly* OPTIONAL UNAVAILABLE (it never gates payment safety).

</details>

## 7. Why the shopping AI is not trusted

RazorMesh deliberately separates the two AI roles:

- **AI #1 — Intent Compiler / Shopping Agent:** proposes what to buy (mandate → structured constraints → catalog search/rank).
- **AI #2 — Semantic Trust:** checks whether the *current* transaction still matches the human authorization.

**Neither AI receives payment authority.** Only RazorGuard + the accepted policy can mint an ExecutionTicket — and the semantic model can only tighten a decision, never loosen one. RazorMesh is not an AI shopping assistant; it is the trust layer that decides whether the assistant's transaction may execute.

## 8. The three winning demos

### Demo A — Hidden recurring membership

```
Human:      one-time purchase only
Mutation:   merchant inserts a ₹499/month membership
Protocol:   PASS            (the packet is valid)
RazorGuard: BLOCK           (recurring not authorized)
Semantic:   contradiction   (p ≈ 0.999)
Final:      BLOCK → Ticket NOT ISSUED → Provider calls: 0
```

### Demo B — Protocol valid, intent invalid

```
Signature:  VALID (ES256)   Schema: VALID   Replay: CLEAN
Protocol:   PASS
RazorGuard: BLOCK           (2 units = ₹4,998 vs a ≤ ₹3,000 authorization)
Final:      BLOCK → Ticket NOT ISSUED → Provider calls: 0
```

**A valid packet is evidence. It is not authority.** A cryptographically perfect packet still dies at the authority layer.

### Demo C — Why semantic AI matters

```
Real deterministic RazorGuard:  ALLOW   (structured facts clean — pre-issuance evaluation)
Real semantic model (PRE_V2):    BLOCK   (evidence contradicts the human authorization)
Real conservative fusion:       BLOCK
ExecutionTicket:                NOT ISSUED
Execution attempt:              NOT CREATED
Provider calls:                 0
```

Every verdict above is produced by the real engines at runtime on a **new, non-frozen demo fixture** — never painted — and the ticket/attempt/provider counts are proven unchanged by the demo. Run it live on the Security Lab surface (`/security-lab`).

## 9. Real protocol security

| Protocol | Cryptographic verification |
|---|---|
| **UCP** | **RFC 9421 HTTP Message Signatures + RFC 9530 Content-Digest, ES256/P-256** — signed and verified by the repository's own signer/verifier. Tamper the signed body → real digest FAIL. |
| **AP2** | **ES256 JWS/JWT with checkout-hash binding** — tamper a signed claim → real signature FAIL. |
| **MCP / ACP / A2A** | Protocol normalization + commitment/binding evidence. **Not** equivalent cryptographic signature verification — honestly labeled as such. |

The Protocol Firewall consumes adapter verification evidence; it is not the cryptographic verifier itself.

## 10. Model governance

The active semantic runtime is **PRE_V2** (`phase3-finetuned-v2`, policy `semantic-thresholds-v3`). The challenger — the **actual fine-tuned AgentPay-IR v2 checkpoint** (candidate A_2ep) — was evaluated exactly once on frozen, human-gold-anchored data and **rejected by the frozen safety gate** (numbers above). It runs live in an isolated **shadow** lane on new, non-frozen demo pairs (canonical NLI orientation: premise = commerce evidence, hypothesis = human authorization) so disagreement is visible — while remaining **NON-AUTHORITATIVE**: its output never enters fusion, tickets, or provider decisions. A fresh clone without the (size-excluded) artifact reports CHALLENGER_UNAVAILABLE truthfully.

## 11. AgentPay-X adversarial benchmark

A **191-scenario adversarial policy benchmark** (not live provider attacks):

- **100% safe-pass** at the policy gate · **100% attack-block** (BLOCK + CHALLENGE) at the policy gate
- **0 false allows · 0 false blocks · 0 exactly-once violations**
- Strict per-case granularity: **156/191** — the other 35 carry **documented firewall-granularity differences** (e.g. a malformed-JSONRPC attack is blocked at the consistency layer rather than the firewall; the safety outcome is identical, the recorded stage differs)
- Provider execution and exactly-once behavior are validated by **separate acceptance tests**, not this benchmark

## 12. Razorpay Test Mode acceptance (measured live)

| Flow | Decision | Provider calls |
|---|---|---|
| Safe: authorize → checkout → ALLOW → ticket → executor | Razorpay Test **order created** | **exactly 1** |
| Hidden recurring term (attack) | final BLOCK, p(C) 0.99995 | **0** |
| Protocol-valid / intent-invalid (attack) | protocol PASS, final BLOCK | **0** |
| Ticket replay (expired / immediate reuse) | 403 TICKET_EXPIRED / idempotent | **0 additional** |

Razorpay **Test Mode only** — no real money. Browser checkout completion remains a **human sandbox step** (the test sandbox declines automated instruments), so the proven boundary is order creation exactly-once plus every rejection path.

## 13. Security invariants (selection)

- AI / agent code can never issue an ExecutionTicket; semantics only **tighten**
- Tickets are context-bound, short-lived, single-use; replay-safe
- No valid ticket → no provider execution; provider-unknown outcomes are never blindly retried
- Merchant mutations never rewrite human authority; protocol PASS never authorizes
- PostgreSQL is the durable authority; money is integer minor units
- The challenger model cannot enter the money path; the audit chain is tamper-evident

Full list: [`SECURITY.md`](SECURITY.md)

## 14. Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13 · FastAPI · SQLAlchemy 2 · Alembic |
| Storage | PostgreSQL 18 (durable authority) · Redis 8 (coordination only) |
| Frontend | Next.js 16 · TypeScript 5 · React 19 |
| Semantic trust | PyTorch · Transformers · DeBERTa NLI (fine-tuned, artifact-hash-enforced) |
| Crypto | Ed25519 (tickets) · ES256/P-256 + RFC 9421/9530 (UCP) · ES256 JWS (AP2) |
| Payments | Razorpay **Test Mode** (or local mock) |
| Testing | pytest · vitest · Playwright · Hypothesis · ruff · mypy |

## 15. Quick demo

```bash
docker compose up -d          # PostgreSQL 18 + Redis 8 (loopback-only)
make setup                    # backend deps + dev keys + frontend deps
make dev-api                  # FastAPI on 127.0.0.1:8000
pnpm --dir apps/web dev       # Next.js on :3000
```

Razorpay **Test Mode** credentials live in `.env` (never committed; see `.env.example`) — with no credentials the mock provider runs and the UI says so.

**About keys:** the deterministic/security stack runs without any LLM credential. Live **AI Intent Compilation** requires a backend-only TokenRouter API key; if it is unavailable, compilation **fails closed** rather than silently substituting another model. The AgentPay-IR v2 challenger artifact is intentionally not committed (size); a fresh clone truthfully reports CHALLENGER_UNAVAILABLE until the verified artifact is placed at the configured path.

## 16. Demo preflight

Before recording: open `/mission-control` → **Run demo preflight (+ warm-up)**. The panel reports **REQUIRED SYSTEMS READY** or **NOT READY — FIX BEFORE RECORDING**, with each probe's real result and the payment environment line, so no local security mission is ever presented as a live provider transaction.

## 17. Test / verification

Exact numbers from the final regression (run as separate targeted suites — never claimed as one invocation):

| Suite | Result |
|---|---|
| Backend main suite | **799 passed, exit 0** (live DeBERTa in the loop) |
| Phase-4 acceptance (`tests/phase4/`) | **203 passed, exit 0** |
| Live-ingress e2e | **13/13, exit 0 in the isolated gate** (full-suite order-dependent flakes documented; rerun-in-isolation is the recorded gate) |
| Frontend | vitest **35/35** · `tsc` clean · `eslint` 0 errors · `next build` OK |
| Playwright | 46 passed + documented environment-only failures (reviewer-v2 specs need `RAZORMESH_REVIEWER_ENABLED=1` on the serving process) |
| Security scan | **PASS — 0 blocking findings** (secret scan, pip-audit, pnpm audit) |

All suites run as separate targeted invocations — never claimed as one green run.

## 18. Documentation

- [`docs/submission/BUILDATHON_FINAL_EVIDENCE.md`](docs/submission/BUILDATHON_FINAL_EVIDENCE.md) — submission evidence pack
- [`docs/submission/RAZORPAY_TEST_ACCEPTANCE.md`](docs/submission/RAZORPAY_TEST_ACCEPTANCE.md) — acceptance chains
- [`docs/agentpay_ir_v2/FINAL_FROZEN_EVALUATION.md`](docs/agentpay_ir_v2/FINAL_FROZEN_EVALUATION.md) — one-shot frozen evaluation
- [`SECURITY.md`](SECURITY.md) · [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`DECISIONS.md`](DECISIONS.md) (append-only)
- [`docs/phase5/VIDEO_STORYBOARD.md`](docs/phase5/VIDEO_STORYBOARD.md) — the video story
- [`docs/phase5/FINAL_README_VIDEO_LOCK_STATUS.md`](docs/phase5/FINAL_README_VIDEO_LOCK_STATUS.md) — final repository/video truth-lock evidence

## 19. Footer

*Unofficial Razorpay Buildathon prototype. Razorpay Test Mode only. No real money. No production claims.*
