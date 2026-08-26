# Landing Page — Shape Brief

**Source brief:** `RazorMesh_UI_Redesign_Master_Prompt.md` §3–§9
**Surface:** `/` (home) — `apps/web/src/app/page.tsx`
**Mode:** **Persuade** (master prompt §2, §9.A)
**Aesthetic era pinned by brief:** cinematic, institutional, intelligent, restrained, security-first, premium.
**Impeccable brief wins over generic defaults:** Inter, pure black/white/gray-300, raw undimmed video, restrained liquid glass — all intentional, none to be "fixed" by a generic rule (master prompt §2).

## 1. Hero composition (must match the supplied video reference)

### Layered z-stack (master prompt §18 — explicit no-overlay regression)
```
hero (viewport)
├── <video> absolute inset-0 z-0   ← raw, no overlay
└── <div.content> relative z-10    ← bottom-aligned, two-column on lg
```

Forbidden hero siblings: `bg-black/xx` overlay, gradient overlay, absolute inset-0 dimmer, full-screen `::before`/`::after` dimming the video. Liquid-glass pseudo-elements are allowed only on glass elements themselves.

### Video attributes (master prompt §3)
- src: `https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260403_050628_c4e32401-fab4-4a27-b7a8-6e9291cd5959.mp4`
- `autoPlay loop muted playsInline`, no controls, no audio.
- `object-fit: cover`, fills the viewport.
- `preload="metadata"` (or `preload="auto"` with the first frame painted as a black fallback before the network resolves).
- `<noscript>` + black fallback if the network fails.
- Decorative → `aria-hidden="true"`, `tabIndex={-1}`.
- Black page background as load/failure fallback only.

### Typography
- Inter (300, 400, 500, 600) loaded from Google Fonts via `<link>` in `app/layout.tsx`.
- `body { font-family: 'Inter', sans-serif; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }`.

### Liquid glass (single canonical class — master prompt §3)
`.liquid-glass` with the supplied background-blend-mode, backdrop-filter blur(4px), inset shadow, and the `::before` border mask. Used only on: navbar pill, secondary CTA, and the right tag. Not used on the hero content wrapper.

### Restrained palette
- `--rm-bg: #000000`
- `--rm-fg: #ffffff`
- `--rm-muted: #d1d5db` (gray-300)
- `--rm-divider: rgba(255, 255, 255, 0.08)`
- `--rm-glass: rgba(0, 0, 0, 0.4)` (locked to the canonical liquid-glass formula)
- `--rm-focus: #ffffff` (visible against pure black)
- No tints. No purple. No gradients on UI surfaces (only on the canonical glass border).

## 2. Navbar (master prompt §4)

- Outer wrapper: `px-6 md:px-12 lg:px-16` (mobile → tablet → desktop gutters); `pt-6`.
- Bar: `.liquid-glass`, `rounded-xl`, `px-4 py-2`, flex items-center justify-between.
- Left: `RAZORMESH`, `text-2xl font-semibold tracking-tight`.
- Center (md+ only): Story / Architecture / Security / Demo links, `text-sm`, `gap-8`, hover gray-300.
- Right: `Start a Chat` (reference copy) → `Launch Demo` (RazorMesh copy), white/black, `px-6 py-2 rounded-lg text-sm font-medium`, hover gray-100.
- Below md: center links hidden, primary CTA remains visible.
- Keyboard traversal + visible focus ring preserved.

## 3. Hero content (master prompt §5)

- Wrapper: same horizontal gutters as nav, flex column filling the remaining viewport, content at bottom, `pb-12 lg:pb-16`.
- lg+: two-column grid, equal columns, `items-end`.
- Heading: `text-4xl md:text-5xl lg:text-6xl xl:text-7xl`, `font-normal`, `mb-4`, `letter-spacing: -0.04em`.
- Subheading: `text-base md:text-lg`, gray-300, `mb-5`.
- CTAs: `flex-wrap gap-4` row.
  - Primary: `Launch Demo` — white/black, `px-8 py-3 rounded-lg font-medium`.
  - Secondary: `Explore Architecture` — liquid-glass, white text, `px-8 py-3 rounded-lg font-medium`, hover white-bg/black-text.
- Right tag (lg+ only): bottom-right of grid, liquid-glass `px-6 py-3 rounded-xl`, `text-lg md:text-xl lg:text-2xl font-light`, copy: `Intent. Verification. Execution.`.

## 4. Motion (master prompt §5)

- `AnimatedHeading`: split by `\n`, then into characters. Each character: `inline-block`, `opacity 0 → 1`, `translateX(-18px) → 0`, `500ms transition`, `charDelay 30ms`, global initial delay `200ms`, delay formula `(lineIndex * lineLength * charDelay) + (charIndex * charDelay)`. Spaces render as `\u00A0`. `prefers-reduced-motion: reduce` → render the final state immediately, no stagger.
- `FadeIn`: opacity 0 → 1 via `setTimeout(delay)`, then `transition-opacity`, configurable duration, cleanup on unmount. Reduced motion → immediate.
- Subheading FadeIn: delay 800ms, duration 1000ms.
- CTA row FadeIn: delay 1200ms, duration 1000ms.
- Right tag FadeIn: delay 1400ms, duration 1000ms.

## 5. Rebrand copy (master prompt §6)

- Logo: `RAZORMESH`.
- Heading: `Agentic commerce,\nwithout blind trust.`
- Subheading: `RazorMesh verifies intent, semantics, and execution before an AI agent can move money.`
- Primary CTA: `Launch Demo` → `/buyer`.
- Secondary CTA: `Explore Architecture` → `/#architecture` (anchor into the architecture section on the same landing page).
- Right tag: `Intent. Verification. Execution.`
- Navbar links: `Story` / `Architecture` / `Security` / `Demo`.
  - `Story` → `/#problem`
  - `Architecture` → `/#architecture`
  - `Security` → `/#security-lab`
  - `Demo` → `/buyer`

## 6. Below the hero (master prompt §8)

Editorial structure, not a feature-card wall. Sections, in order:

### A. Problem (`#problem`)
- Heading: `AI agents can transact. Trust is the missing layer.`
- Three short paragraphs: model output ≠ authorization; valid protocol/API calls can still violate human intent; retries, context drift, concurrency create payment risk.

### B. How RazorMesh works (`#how`)
- Disciplined sequence: `01 Intent → 02 Verify → 03 Authorize → 04 Execute → 05 Prove`
- Each step ties to a real system component (Intent Compiler, RazorGuard, Human Confirmation, Trusted Executor, Evidence Ledger).

### C. Architecture (`#architecture`)
- Flow line: `Human Intent → Intent Compiler → Human Confirmation → RazorGuard → Semantic Verifier → Execution Ticket → Razorpay Test Mode → Audit`
- Inline SVG diagram (restrained, black/white).

### D. Proof, not promises (`#proof`)
- Only metrics traceable to current committed Phase-2/3 evidence.
- Verifiable per master prompt §20 from `docs/PHASE3_COMPLETION_REPORT.md` + `docs/PHASE3_NLI_FINETUNED_METRICS.json`:
  - 522 backend tests (pytest, clean-room M49)
  - 12 vitest frontend tests + 5 Playwright E2E (in scope of redesign)
  - 0 secrets leaked (security-check)
  - Fine-tuned NLI: 31/31 human contradictions BLOCKED (heldout); 0 unsafe entailments on 119 human contradictions
  - RazorGuard never ALLOWS without an EvidenceLedger-verified ticket (architectural, evidenced)
- All numbers carry source link.

### E. Security Lab preview (`#security-lab`)
- Concrete scenario:
  - Human: `No recurring payment.`
  - Evidence: `Free trial renews at ₹499/month.`
  - Hard rules: PASS
  - Semantic verifier: CONTRADICTION
  - Final: BLOCK
- CTA: `Open Security Lab` → `/security-lab`.

### F. Future interoperability teaser (`#future`)
- Plain prose: designed for protocol adapters / heterogeneous agentic commerce. **No** MCP/UCP/AP2/ACP compliance claims.

### G. Minimal footer
- Project name, real navigation, public GitHub if appropriate. No fake corporate address.

## 7. Other routes (Operate mode — master prompt §9.B)

- Same Inter, same black/white base, white-alpha dividers, same radii/button language, same focus/motion philosophy.
- Restrained glass only on nav and floating emphasis.
- Operate pages prioritize readability and state clarity over atmosphere.
- No cinematic video behind Buyer / Security Lab / Audit / Merchant pages.
- Route transitions: `opacity 0 → 1` + `translateY(8px) → 0`, 200ms, restrained easing, reduced-motion = instant.

## 8. Anti-AI copy rules (master prompt §11)

- Short, concrete, technical, evidence-driven.
- Bad: "revolutionize", "unlock the power", "cutting-edge", "seamless" repetition, fake social proof.
- Good: `The AI proposes. RazorGuard authorizes. The trusted executor executes.` / `Valid signatures are not enough if the transaction no longer matches human intent.`

## 9. Non-goals (master prompt §1, §6, §11, §20)

- No fake customers, production claims, revenue, adoption, certifications, or protocol compliance.
- No "official Razorpay font" or private brand token unless publicly verified.
- No purple/indigo gradients, glowing blobs, generic bento walls, icon tiles above every heading, excessive pills, glass on every panel, card-inside-card layouts, fake testimonials, invented customers/metrics, stock illustrations, emoji decoration, "AI-powered" filler, hacker-terminal clichés, decorative effects with no product meaning.

## 10. Routes & links inventory (master prompt §7)

- `/` landing (this surface) — `RAZORMESH` logo, `Launch Demo` primary, `Explore Architecture` secondary.
- `/buyer` Demo — `Launch Demo` lands here.
- `/security-lab` Security Lab — `Open Security Lab` + navbar `Security` land here.
- `/` anchor `#architecture` — secondary CTA.
- `/` anchor `#problem` — navbar `Story`.
- `/` anchor `#security-lab` — navbar `Security` alternate.
- `/` anchor `#proof` — section link from "how it works" / "architecture".
- No dead `href="#"` links.

## 11. Out of scope for this milestone (deferred to later gates)

- Impeccable `/impeccable document` recording the final visual world in `DESIGN.md` happens at **UI-10** (after the visual language is proven) and again at **UI-17** (final polish).
- `/impeccable typeset`, `/impeccable layout`, `/impeccable animate hero`, `/impeccable adapt`, `/impeccable live`, `/impeccable critique`, `/impeccable audit`, `/impeccable optimize`, `/impeccable extract`, `/impeccable harden`, `/impeccable polish` are routed to their respective gates below.

## 12. Verdict

**UI-02 PASS.** Persuade-mode landing brief persisted; Operate-mode app-shell contract persisted; routes and copy mapped; anti-AI rules + non-goals + evidence rule + reduced-motion rule captured before any code is touched.
