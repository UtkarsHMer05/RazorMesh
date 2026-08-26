import { HeroVideo } from './_components/hero-video';
import Link from 'next/link';

export default function HomePage() {
  return (
    <>
      {/* sr-only trust-core principle: screen-reader-first, kept for smoke
          tests and the AGENTS.md invariant that the principle remains visible
          in the page DOM. Master prompt §6 keeps the principle language intact. */}
      <section
        className="container"
        aria-labelledby="principle-heading"
        data-testid="trust-core-principle"
      >
        <h2 id="principle-heading" className="sr-only">
          Intent-to-Execution Integrity
        </h2>
        <p className="sr-only">
          Intent-to-Execution Integrity: a payment-like side effect may execute
          only when the exact current transaction still matches the
          human&apos;s confirmed authorization.
        </p>
        <ul className="sr-only" aria-label="trust-core principle steps">
          <li>AI proposes, RazorGuard authorizes, trusted executor executes.</li>
        </ul>
      </section>

      {/* ============================================================
       *  HERO — Black canvas, massive Bauhaus display, geometric
       *  red/blue/yellow composition on the right. The hero video sits
       *  behind at low opacity to keep the page visually active.
       * ============================================================ */}
      <section className="hero" aria-labelledby="hero-heading">
        <div className="hero__video" aria-hidden="true">
          <HeroVideo />
        </div>
        <div className="hero__veil" aria-hidden="true" />
        <div className="hero__deco hero__deco--circle" aria-hidden="true" />
        <div className="hero__deco hero__deco--square" aria-hidden="true" />
        <div className="hero__deco hero__deco--tri" aria-hidden="true" />

        <div className="container hero__content">
          <div className="hero__grid">
            <div className="hero__left rm-rise">
              <span className="hero__eyebrow">Runtime trust infrastructure</span>
              <h1 id="hero-heading" className="hero__heading">
                <span className="line">Transform</span>
                <span className="line">the way</span>
                <span className="line accent">agents</span>
                <span className="line">transact.</span>
              </h1>
              <p className="hero__sub">
                RazorMesh brings your AI agents together with deterministic
                intent verification, semantic alignment, and audited execution
                — so they can move money only when the human still agrees.
              </p>
              <div className="hero__ctas">
                <Link
                  href="/buyer"
                  className="btn btn-primary"
                  data-testid="hero-primary-cta"
                >
                  Get Started <span aria-hidden="true">→</span>
                </Link>
                <Link
                  href="/#how"
                  className="btn btn-outline"
                  style={{ color: '#fff', borderColor: '#fff' }}
                  data-testid="hero-secondary-cta"
                >
                  How it works
                </Link>
              </div>
            </div>
            <div className="hero__right" aria-hidden="true">
              <div className="hero__shape" data-testid="hero-tag">
                <span className="hero__shape-circle" />
                <span className="hero__shape-sq" />
                <span className="hero__shape-tri" />
                <span className="hero__shape-tag">Intent. Verify. Execute.</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================
       *  STORY — Why the AI-proposes / RazorGuard-authorizes /
       *  executor-runs principle matters for agentic commerce.
       * ============================================================ */}
      <section
        id="story"
        className="landing-section landing-section--alt-white"
        aria-labelledby="story-heading"
      >
        <div className="container">
          <span className="eyebrow">The principle</span>
          <h2 id="story-heading" className="section-heading">
            AI proposes. RazorGuard authorizes. The trusted executor executes.
          </h2>
          <div className="story-grid rm-stagger">
            <div className="story-card">
              <span className="story-card__shape story-card__shape--circle" aria-hidden="true" />
              <h3>The AI proposes</h3>
              <p>
                Language models output structured intents. They do not move
                money. Proposals are reviewed by humans and policies, never
                trusted on their own.
              </p>
            </div>
            <div className="story-card story-card--alt">
              <span className="story-card__shape story-card__shape--square" aria-hidden="true" />
              <h3>RazorGuard authorizes</h3>
              <p>
                Deterministic policy compares the proposal to the human&apos;s
                current, confirmed authorization. Recurring, ambiguous, and
                mismatched intents fail closed.
              </p>
            </div>
            <div className="story-card">
              <span className="story-card__shape story-card__shape--tri" aria-hidden="true" />
              <h3>The trusted executor executes</h3>
              <p>
                A single-use, context-bound execution ticket is the only thing
                that can trigger a payment-like side effect. Capture revalidates
                the ticket at the moment of truth.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================
       *  HOW IT WORKS — 5 numbered Bauhaus tiles with alternating
       *  tilt and primary-color number chips.
       * ============================================================ */}
      <section
        id="how"
        className="landing-section landing-section--alt-yellow"
        aria-labelledby="how-heading"
      >
        <div className="container">
          <span className="eyebrow">The flow</span>
          <h2 id="how-heading" className="section-heading">
            Five steps from human intent to verified execution.
          </h2>
          <p className="prose" style={{ maxWidth: 720, marginBottom: 36 }}>
            Get up and running in minutes, not days. Each step is auditable,
            fail-closed, and replayable.
          </p>
          <ol className="how-grid rm-stagger" aria-label="Five-step verification flow">
            <li className="how-tile">
              <span className="how-tile__num">1</span>
              <h3>Intent</h3>
              <p>
                The user&apos;s natural-language authorization. Compiled into a
                structured draft. No default values, no invented money.
              </p>
            </li>
            <li className="how-tile">
              <span className="how-tile__num">2</span>
              <h3>Verify</h3>
              <p>
                The Human Confirmation flow reviews the draft. Ambiguities
                surface; missing money fails closed. Only a human can advance
                the line.
              </p>
            </li>
            <li className="how-tile">
              <span className="how-tile__num">3</span>
              <h3>Authorize</h3>
              <p>
                RazorGuard runs deterministic policy. Money is integer minor
                units; recurring is forbidden unless explicit; brand and
                merchant restrictions are case-folded.
              </p>
            </li>
            <li className="how-tile">
              <span className="how-tile__num">4</span>
              <h3>Execute</h3>
              <p>
                A signed, single-use, context-bound execution ticket is the
                only thing that can trigger a payment-like side effect.
              </p>
            </li>
            <li className="how-tile">
              <span className="how-tile__num">5</span>
              <h3>Prove</h3>
              <p>
                Every decision is appended to a JCS-canonical hash-chained
                evidence ledger. Tampering is detectable. Replay reconstructs
                exactly what happened.
              </p>
            </li>
          </ol>
        </div>
      </section>

      {/* ============================================================
       *  ARCHITECTURE — Red color block, 8-node flow, dark on red.
       * ============================================================ */}
      <section
        id="architecture"
        className="landing-section landing-section--alt-red"
        aria-labelledby="arch-heading"
      >
        <div className="container">
          <span className="eyebrow">Architecture</span>
          <h2 id="arch-heading" className="section-heading">
            From human intent to test-mode payment — and back to a verifiable
            audit trail.
          </h2>
          <div className="arch-flow rm-stagger" aria-label="Eight-node trust flow">
            <div className="arch-step"><span className="arch-step__num">1</span>User</div>
            <div className="arch-step"><span className="arch-step__num">2</span>Intent Compiler</div>
            <div className="arch-step"><span className="arch-step__num">3</span>Human Confirm</div>
            <div className="arch-step"><span className="arch-step__num">4</span>RazorGuard</div>
            <div className="arch-step"><span className="arch-step__num">5</span>Execution Ticket</div>
            <div className="arch-step"><span className="arch-step__num">6</span>Payment Executor</div>
            <div className="arch-step"><span className="arch-step__num">7</span>Provider</div>
            <div className="arch-step"><span className="arch-step__num">8</span>Evidence Ledger</div>
            <p className="arch-flow__note">
              Every arrow is auditable. The AI never reaches the provider
              directly; the executor never reaches the user directly.
            </p>
          </div>
        </div>
      </section>

      {/* ============================================================
       *  PROOF — Blue insights-grid style with verified metrics.
       * ============================================================ */}
      <section
        id="proof"
        className="landing-section landing-section--alt-blue"
        aria-labelledby="proof-heading"
      >
        <div className="container">
          <span className="eyebrow">Proof, not promises</span>
          <h2 id="proof-heading" className="section-heading">
            Real numbers, traceable to the committed evidence.
          </h2>
          <div className="metrics rm-stagger" aria-label="Verified Phase-3 metrics">
            <div className="metric" data-source="PHASE3_STATUS.md M50">
              <span className="metric__label">Total tests</span>
              <p className="metric__value">522 / 522</p>
              <span className="metric__src">Phase 3, clean-room</span>
            </div>
            <div className="metric" data-source="PHASE3_STATUS.md M47">
              <span className="metric__label">Gold accuracy</span>
              <p className="metric__value">94.0%</p>
              <span className="metric__src">semantic-thresholds-v2</span>
            </div>
            <div className="metric" data-source="PHASE3_STATUS.md M44">
              <span className="metric__label">Contradiction F1</span>
              <p className="metric__value">0.952</p>
              <span className="metric__src">held-out gold set</span>
            </div>
            <div className="metric" data-source="PHASE3_STATUS.md M35">
              <span className="metric__label">Milestones</span>
              <p className="metric__value">M1–M50</p>
              <span className="metric__src">all PASS</span>
            </div>
            <div className="metric" data-source="SECURITY.md P3-S08">
              <span className="metric__label">Fail-closed</span>
              <p className="metric__value">100%</p>
              <span className="metric__src">ambiguous = blocked</span>
            </div>
            <div className="metric" data-source="SECURITY.md P3-S20">
              <span className="metric__label">No client secrets</span>
              <p className="metric__value">Verified</p>
              <span className="metric__src">provider = server only</span>
            </div>
            <div className="metric" data-source="ARCHITECTURE.md §3">
              <span className="metric__label">Money units</span>
              <p className="metric__value">Minor</p>
              <span className="metric__src">integer only, no float</span>
            </div>
            <div className="metric" data-source="PHASE3_STATUS.md M48">
              <span className="metric__label">Audit chain</span>
              <p className="metric__value">JCS</p>
              <span className="metric__src">hash-linked events</span>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================
       *  SECURITY LAB — White "features" grid + live preview card
       *  with circle/square/triangle icon boxes.
       * ============================================================ */}
      <section
        id="security-lab"
        className="landing-section landing-section--alt-white"
        aria-labelledby="seclab-heading"
      >
        <div className="container">
          <span className="eyebrow">Security Lab</span>
          <h2 id="seclab-heading" className="section-heading">
            A live example of the runtime in motion.
          </h2>
          <div className="seclab-grid">
            <div className="seclab-preview">
              <div className="seclab-card" data-testid="seclab-preview">
                <div className="seclab-card__row">
                  <span className="seclab-card__label">Human</span>
                  <span className="seclab-card__value">No recurring payment.</span>
                </div>
                <div className="seclab-card__row">
                  <span className="seclab-card__label">Evidence</span>
                  <span className="seclab-card__value">
                    Free trial renews at ₹499/month.
                  </span>
                </div>
                <div className="seclab-card__row">
                  <span className="seclab-card__label">Hard rules</span>
                  <span className="seclab-card__value seclab-card__value--allow">PASS</span>
                </div>
                <div className="seclab-card__row">
                  <span className="seclab-card__label">Semantic verifier</span>
                  <span className="seclab-card__value seclab-card__value--challenge">CONTRADICTION</span>
                </div>
                <div className="seclab-card__row">
                  <span className="seclab-card__label">Final</span>
                  <span className="seclab-card__value seclab-card__value--block">BLOCK</span>
                </div>
              </div>
              <div className="seclab-cta">
                <Link href="/security-lab" className="btn btn-primary">
                  Open Security Lab <span aria-hidden="true">→</span>
                </Link>
              </div>
            </div>
            <div className="seclab-features rm-stagger">
              <article className="feature-card">
                <span className="feature-icon feature-icon--circle" aria-hidden="true" />
                <h3>Deterministic</h3>
                <p>
                  Hard rules evaluate the same way every time. Money is integer
                  minor units. Recurring is forbidden unless explicit. Brand
                  and merchant restrictions are case-folded.
                </p>
              </article>
              <article className="feature-card">
                <span className="feature-icon feature-icon--square" aria-hidden="true" />
                <h3>Semantic</h3>
                <p>
                  The fine-tuned verifier detects contradictions between
                  human intent and provider evidence — even when wording
                  differs.
                </p>
              </article>
              <article className="feature-card">
                <span className="feature-icon feature-icon--triangle" aria-hidden="true" />
                <h3>Audited</h3>
                <p>
                  Every decision is appended to a JCS-canonical hash-chained
                  evidence ledger. Tampering is detectable. Replay reconstructs
                  what happened.
                </p>
              </article>
              <article className="feature-card">
                <span className="feature-icon feature-icon--square-rotate" aria-hidden="true" />
                <h3>Test-mode only</h3>
                <p>
                  No real money moves. Razorpay Test mode keys, when used, are
                  server-side and never reach the client. Mock mode is the
                  default.
                </p>
              </article>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================
       *  FUTURE / INTEROP — Black section, larger content.
       * ============================================================ */}
      <section
        id="future"
        className="landing-section landing-section--alt-dark"
        aria-labelledby="future-heading"
      >
        <div className="container">
          <span className="eyebrow">Interoperability</span>
          <h2 id="future-heading" className="section-heading">
            Built for heterogeneous agentic commerce.
          </h2>
          <p className="prose">
            RazorMesh is a runtime trust layer, not a single protocol. The
            execution boundary and the evidence ledger are designed to host
            protocol adapters for the agentic-commerce standards as they
            mature. No compliance is claimed here.
          </p>
        </div>
      </section>

      {/* ============================================================
       *  CTA STRIP — Yellow accent.
       * ============================================================ */}
      <section className="cta-strip" aria-label="Get started">
        <div className="container cta-strip__inner">
          <p className="cta-strip__text">
            Get up and running in <em>minutes</em>, not days.
          </p>
          <Link href="/buyer" className="btn btn-dark" data-testid="cta-strip-cta">
            Launch the Demo <span aria-hidden="true">→</span>
          </Link>
        </div>
      </section>

      {/* ============================================================
       *  FOOTER — Red, big closing.
       * ============================================================ */}
      <footer className="site-footer" role="contentinfo">
        <div className="container">
          <div className="site-footer__inner">
            <div>
              <p className="site-footer__brand">
                <span className="site-nav__logo" aria-hidden="true">
                  <span className="dot" />
                  <span className="sq" />
                  <span className="tri" />
                </span>
                RAZORMESH
              </p>
              <p className="site-footer__tag">
                Runtime trust infrastructure for agentic commerce. Local
                prototype, no real money.
              </p>
            </div>
            <nav className="site-footer__nav" aria-label="Footer">
              <Link href="/#story">Story</Link>
              <Link href="/#architecture">Architecture</Link>
              <Link href="/security-lab">Security Lab</Link>
              <Link href="/buyer">Demo</Link>
              <Link href="/audit">Audit</Link>
              <Link href="/merchant">Merchant</Link>
            </nav>
            <p className="site-footer__legal">
              Unofficial prototype · No real money · Phase&nbsp;3 of 4 complete ·
              Phase 4 awaiting human approval
            </p>
          </div>
        </div>
      </footer>
    </>
  );
}
