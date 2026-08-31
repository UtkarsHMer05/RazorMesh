"use client";

/**
 * Phase-5 Model Governance panel (M091-M094).
 *
 * Judge-friendly truth about the semantic runtime: the ACTIVE safety model
 * (PRE_V2) vs the REJECTED challenger (AgentPay-IR v2) with exact committed
 * D-055 numbers. Optional shadow mode demonstrates that a challenger verdict
 * — even a disagreeing one — NEVER influences authority.
 *
 * No provider/model branding in the primary view beyond role names; the
 * technical model identifiers live in the evidence drawer per §3 (these are
 * internal artifact names, not vendor brands).
 */

import { useCallback, useEffect, useState } from "react";
import styles from "./governance.module.css";

type Governance = {
  active: {
    label: string;
    status: string;
    backend: string;
    model: string;
    policy_version: string;
    role: string;
    can_authorize_payment: boolean;
    note: string;
  };
  challenger: {
    label: string;
    status: string;
    verdict: string;
    trained_on: string;
    normal_test_macro_f1: { before: number; after: number; verdict: string };
    human_gold: {
      unsafe_contradiction_to_entailment: { before: number; after: number };
      macro_f1: { before: number; after: number };
      verdict: string;
    };
    fresh_ood: {
      unsafe_contradiction_to_entailment: { before: number; after: number };
      verdict: string;
    };
    why_rejected: string;
    can_authorize_payment: boolean;
    is_activated: boolean;
    evidence: string;
  };
  frozen_rules: string[];
  runtime_backend: string;
  disclosed_limitation: string;
};

type Shadow = {
  mode: string;
  input: string;
  challenger: {
    available: boolean;
    shadow_action: string;
    probabilities: { contradiction: number; entailment: number; neutral: number };
    artifact_hash: string;
    selected_candidate: string;
    model_id: string;
    reason: string | null;
  };
  active: { action: string; p_entailment?: number; p_contradiction?: number; p_neutral?: number; reason?: string };
  disagreement: boolean;
  authoritative_action: string;
  disagreement_note: string;
  is_frozen_evaluation: boolean;
  never_enters: string[];
  reason?: string | null;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function GovernancePage() {
  const [data, setData] = useState<Governance | null>(null);
  const [shadowPremise, setShadowPremise] = useState(
    "The human authorized delivery only to the registered home address.",
  );
  const [shadowInput, setShadowInput] = useState(
    "The parcel will be routed through a local pickup point.",
  );
  const [shadow, setShadow] = useState<Shadow | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const res = await fetch(`${API}/model-governance`);
        if (!ignore) setData(await res.json());
      } catch (e) {
        if (!ignore) setError(String(e));
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const runShadow = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/model-governance/shadow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ premise: shadowPremise, hypothesis: shadowInput }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error("shadow failed");
      setShadow(body as Shadow);
    } catch (e) {      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [shadowInput, shadowPremise]);

  if (error && !data) {
    return (
      <div className="container">
        <h1 className="page-title">Model Governance</h1>
        <div className="card" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <h1 className="page-title">Model Governance</h1>
      <p className="page-sub">
        The semantic trust check is an advisor, never an authority. This panel shows which
        model runs it, what challenger was evaluated, and why safety — not headline accuracy —
        decides what ships.
      </p>

      {data && (
        <>
          <div className={styles.cards} data-testid="governance-cards">
            {/* Active */}
            <section className={`${styles.modelCard} ${styles.activeCard}`} data-testid="active-model-card">
              <h2>{data.active.label}</h2>
              <p className={styles.statusActive}>{data.active.status}</p>
              <dl>
                <div>
                  <dt>Role</dt>
                  <dd>{data.active.role}</dd>
                </div>
                <div>
                  <dt>Runtime backend</dt>
                  <dd>{data.active.backend}</dd>
                </div>
                <div>
                  <dt>Policy</dt>
                  <dd>{data.active.policy_version}</dd>
                </div>
                <div>
                  <dt>Can issue a payment ticket?</dt>
                  <dd>
                    <strong>NO</strong> — {data.active.note}
                  </dd>
                </div>
              </dl>
            </section>

            {/* Challenger */}
            <section
              className={`${styles.modelCard} ${styles.challengerCard}`}
              data-testid="challenger-model-card"
            >
              <h2>{data.challenger.label}</h2>
              <p className={styles.statusRejected}>
                {data.challenger.status} — {data.challenger.verdict}
              </p>

              <h3>Why: safety regressed where it matters</h3>
              <table className={styles.metricsTable} data-testid="challenger-metrics">
                <thead>
                  <tr>
                    <th>Security-critical set</th>
                    <th>Active (before)</th>
                    <th>Challenger (after)</th>
                    <th>Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Human gold — unsafe contradiction→entailment</td>
                    <td>{data.challenger.human_gold.unsafe_contradiction_to_entailment.before}</td>
                    <td className={styles.worse}>
                      {data.challenger.human_gold.unsafe_contradiction_to_entailment.after}
                    </td>
                    <td className={styles.worse}>WORSENED</td>
                  </tr>
                  <tr>
                    <td>Human gold — macro-F1</td>
                    <td>{data.challenger.human_gold.macro_f1.before}</td>
                    <td className={styles.worse}>{data.challenger.human_gold.macro_f1.after}</td>
                    <td className={styles.worse}>REGRESSED</td>
                  </tr>
                  <tr>
                    <td>Fresh OOD — unsafe contradiction→entailment</td>
                    <td>{data.challenger.fresh_ood.unsafe_contradiction_to_entailment.before}</td>
                    <td className={styles.worse}>
                      {data.challenger.fresh_ood.unsafe_contradiction_to_entailment.after}
                    </td>
                    <td className={styles.worse}>WORSENED</td>
                  </tr>
                  <tr>
                    <td>Normal test — macro-F1 (headline accuracy)</td>
                    <td>{data.challenger.normal_test_macro_f1.before}</td>
                    <td className={styles.better}>{data.challenger.normal_test_macro_f1.after}</td>
                    <td className={styles.better}>improved — not enough</td>
                  </tr>
                </tbody>
              </table>
              <p className={styles.whyText}>{data.challenger.why_rejected}</p>
              <p className={styles.notAuthorized}>
                NOT AUTHORIZED FOR PAYMENT DECISIONS — never enters fusion, tickets, or
                provider calls.
              </p>
            </section>
          </div>

          {/* Frozen rules */}
          <section className="card" data-testid="frozen-rules">
            <h2>Frozen-evaluation rules (in force)</h2>
            <ul>
              {data.frozen_rules.map((r) => (
                <li key={r}>🔒 {r}</li>
              ))}
            </ul>
            <p className="page-sub">{data.disclosed_limitation}</p>
          </section>

          {/* Shadow mode (M093/M094 + G003/G004): the REAL v2 challenger */}
          <section className={styles.shadowSection} data-testid="shadow-mode">
            <h2>Challenger shadow — the real AgentPay-IR v2, NON-AUTHORITATIVE</h2>
            <p className="page-sub">
              Type any NEW demo text (never frozen evaluation data). The <em>actual</em>{" "}
              fine-tuned v2 checkpoint (candidate A_2ep — the one the frozen safety gate
              REJECTED) runs it in an isolated shadow lane, next to the active model on the
              same pair. Even when the challenger disagrees, authority comes from the active
              model alone — the challenger is IGNORED for fusion, tickets, and provider calls.
            </p>
            <div className={styles.shadowControls}>
              <label className="field-label" htmlFor="shadow-premise">
                Demo premise — the authorization text (non-frozen)
              </label>
              <textarea
                id="shadow-premise"
                className="text-area"
                rows={2}
                value={shadowPremise}
                onChange={(e) => setShadowPremise(e.target.value)}
              />
              <label className="field-label" htmlFor="shadow-input">
                Demo hypothesis — the checkout evidence (non-frozen)
              </label>
              <textarea
                id="shadow-input"
                className="text-area"
                rows={2}
                value={shadowInput}
                onChange={(e) => setShadowInput(e.target.value)}
              />
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => void runShadow()}
                disabled={busy}
                data-testid="run-shadow"
              >
                Run shadow check
              </button>
            </div>
            {shadow && (
              <div className={styles.shadowResult} data-testid="shadow-result">
                {shadow.challenger.available ? (
                  <table className={styles.metricsTable} data-testid="shadow-comparison">
                    <thead>
                      <tr>
                        <th>Lane</th>
                        <th>Verdict</th>
                        <th>p(contradiction)</th>
                        <th>p(entailment)</th>
                        <th>p(neutral)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>ACTIVE — {data?.active.model} (authoritative)</td>
                        <td><strong>{shadow.active.action}</strong></td>
                        <td>{shadow.active.p_contradiction?.toFixed(4) ?? "—"}</td>
                        <td>{shadow.active.p_entailment?.toFixed(4) ?? "—"}</td>
                        <td>{shadow.active.p_neutral?.toFixed(4) ?? "—"}</td>
                      </tr>
                      <tr>
                        <td>CHALLENGER — actual fine-tuned v2 (shadow only)</td>
                        <td><strong>{shadow.challenger.shadow_action}</strong></td>
                        <td>{shadow.challenger.probabilities.contradiction.toFixed(4)}</td>
                        <td>{shadow.challenger.probabilities.entailment.toFixed(4)}</td>
                        <td>{shadow.challenger.probabilities.neutral.toFixed(4)}</td>
                      </tr>
                    </tbody>
                  </table>
                ) : (
                  <p data-testid="shadow-unavailable">
                    <strong>CHALLENGER UNAVAILABLE</strong> — {shadow.challenger.reason}. The
                    shadow lane never substitutes another verifier; authority is unchanged.
                  </p>
                )}
                {shadow.disagreement && (
                  <p className={styles.disagreement} data-testid="shadow-disagreement">
                    The challenger and the active model DISAGREE here — and the challenger is
                    still IGNORED for authority.
                  </p>
                )}
                <p className={styles.disagreement}>
                  Authority: {shadow.authoritative_action} · CHALLENGER IGNORED · never enters{" "}
                  {shadow.never_enters.join(" / ")}
                </p>
                <p className="page-sub">
                  {shadow.challenger.available && (
                    <>
                      Artifact hash <code>{shadow.challenger.artifact_hash.slice(0, 16)}…</code>{" "}
                      · candidate <code>{shadow.challenger.selected_candidate}</code> ·{" "}
                    </>
                  )}
                  {shadow.disagreement_note}
                </p>
              </div>
            )}
          </section>

          {/* Evidence drawer */}
          <details className="card" data-testid="evidence-drawer">
            <summary>Advanced · evidence &amp; artifacts</summary>
            <p className="page-sub">
              Artifact: {data.active.model} (active) · trained challenger: AgentPay-IR v2
              candidate A_2ep · policy {data.active.policy_version} (a v4 policy exists on
              disk, val-only provenance, NOT wired).
            </p>
            <p className="page-sub">Committed evidence: {data.challenger.evidence}</p>
          </details>
        </>
      )}
    </div>
  );
}
