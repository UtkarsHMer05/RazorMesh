"use client";

import { SecurityLabMission } from "./SecurityLabMission";

import { useEffect, useState } from "react";

type ScenarioInfo = {
  scenario_id: string;
  family: string;
  description: string;
};

type LabResult = {
  scenario_id: string;
  family: string;
  actual: string;
  passed: boolean;
  detail: string;
  amount_minor: number;
};

type EvidenceEvent = {
  seq: number;
  event_type: string;
  actor: string;
  hash_head: string;
};

type LabRun = {
  total: number;
  passed: number;
  results: LabResult[];
  evidence_tail: EvidenceEvent[];
};

type DemoEvidence = {
  scenario: string;
  run_id: string;
  rejection_stage: string | null;
  rejection_reason: string | null;
  protocol_firewall: string;
  protocol_firewall_reasons: string[];
  razorguard_decision: string;
  semantic_verifier: string;
  semantic_backend: string;
  semantic_model_version: string;
  semantic_probabilities: {
    contradiction: number;
    entailment: number;
    neutral: number;
  };
  semantic_fail_closed: boolean;
  final_decision: string;
  ticket_issued: boolean;
  provider_contacted: boolean;
};

type WhySemanticAi = {
  label: string;
  honest: boolean;
  fixture: {
    provenance: string;
    non_frozen: boolean;
    not_used_for_model_selection: boolean;
    not_used_for_calibration: boolean;
    orientation: string;
    demo_transaction: { intent_id: string; checkout_id: string; fresh_per_run: boolean };
  };
  runtime: { model_id: string; policy_version: string; fail_closed: boolean };
  authority_proof: {
    tickets_before: number;
    tickets_after: number;
    attempts_before: number;
    attempts_after: number;
    provider_calls_before: number;
    provider_calls_after: number;
    ticket_minted: boolean;
    note: string;
  };
  demonstration: {
    pair_id: string;
    aspect: string;
    razorguard: string;
    semantic: string;
    probabilities: { contradiction: number; entailment: number; neutral: number };
    fusion: string;
    ticket: string;
    execution_attempt: string;
    provider_calls: number;
  }[];
  structured_lane_detail: {
    razorguard: string;
    reason_codes: string[];
    policy_version: string;
    note: string;
  };
  story: string;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function SecurityLabPage() {
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [run, setRun] = useState<LabRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState<DemoEvidence | null>(null);
  const [demoBusy, setDemoBusy] = useState<string | null>(null);
  const [whySemantic, setWhySemantic] = useState<WhySemanticAi | null>(null);
  const [whySemanticBusy, setWhySemanticBusy] = useState(false);

  const runWhySemanticAi = async () => {
    setWhySemanticBusy(true);
    setWhySemantic(null);
    try {
      const res = await fetch(`${API}/security-lab/why-semantic-ai`);
      const body = await res.json();
      if (!res.ok) throw new Error("demo failed");
      setWhySemantic(body as WhySemanticAi);
    } catch (e) {
      setError(String(e));
    } finally {
      setWhySemanticBusy(false);
    }
  };

  const runDemo = async (
    slug: "scenario-b-semantic-violation" | "scenario-c-protocol-valid-intent-invalid",
  ) => {
    setDemoBusy(slug);
    setError(null);
    setDemo(null);
    try {
      const res = await fetch(`${API}/phase4/acceptance/demo/${slug}`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      setDemo(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setDemoBusy(null);
    }
  };

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const res = await fetch(`${API}/security-lab/scenarios`);
        if (!res.ok) throw new Error(`scenarios ${res.status}`);
        const body = await res.json();
        if (!ignore) setScenarios(body.scenarios);
      } catch (e) {
        if (!ignore) setError(`Scenario catalog unavailable — is the API running? (${String(e)})`);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const runSuite = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/security-lab/run`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      setRun(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="lab-title">
      <div className="container">
        <h1 className="page-title" id="lab-title">
          Security Lab — Synthetic Attack Simulation
        </h1>
      <p className="page-sub">
        Defensive demonstration only. Scenarios run against this local system&apos;s real
        authorization path; nothing here attacks Razorpay or any third party. Results are
        shown only after backend execution.
      </p>

      <SecurityLabMission />

      {error && (
        <div className="card" role="alert" data-testid="lab-error">
          {error}
        </div>
      )}

      <div className="card" data-testid="scenario-list">
        <h3>Registered synthetic scenarios ({scenarios.length})</h3>
        <ul>
          {scenarios.map((s) => (
            <li key={s.scenario_id}>
              <code>{s.scenario_id}</code> — {s.description}
            </li>
          ))}
        </ul>
        <button onClick={runSuite} disabled={busy}>
          {busy ? "Executing…" : "Execute scenario suite (local, mock provider)"}
        </button>
      </div>

      <div className="card" data-testid="demo-scenarios">
        <h3>Intent firewall — full-pipeline demo</h3>
        <p className="page-sub">
          Runs the real acceptance pipeline (protocol firewall → deterministic RazorGuard →
          semantic verifier → fused decision). SAFE PURCHASE (Scenario A) lives on the{" "}
          <a href="/buyer">Buyer page</a> where a real Razorpay Test payment can complete.
        </p>
        <button
          onClick={() => runDemo("scenario-b-semantic-violation")}
          disabled={demoBusy !== null}
        >
          {demoBusy === "scenario-b-semantic-violation"
            ? "Executing…"
            : "Scenario B — recurring membership the human never authorized"}
        </button>{" "}
        <button
          onClick={() => runDemo("scenario-c-protocol-valid-intent-invalid")}
          disabled={demoBusy !== null}
        >
          {demoBusy === "scenario-c-protocol-valid-intent-invalid"
            ? "Executing…"
            : "Scenario C — protocol-valid, intent-invalid (2 units vs ≤ ₹3,000)"}
        </button>
        <p className="page-sub">
          Disclosed limitation: a recurring term hidden ONLY in untrusted listing text (with a
          clean structured checkout) is not visible to the structured evidence builder — this is
          the known gap the AgentPay-IR v2 training corpus targeted; the v2 candidate was
          evaluated on frozen data and not activated by the safety gate.
        </p>
      </div>

      <div className="card" data-testid="why-semantic-ai">
        <h3>Why semantic AI matters — semantic-only tightening</h3>
        <p className="page-sub">
          If RazorGuard catches everything deterministic, why does the semantic model exist?
          Run this: a FRESH transaction is created and evaluated by the REAL deterministic
          RazorGuard rule engine at the pre-issuance seam — on the structured facts alone it
          ALLOWS (structure alone would proceed to a ticket). Then the REAL active semantic
          model reads the commerce evidence against the human authorization, finds the
          continuing-service contradiction, and conservative fusion BLOCKs — so the
          ticket-issuance stage is never reached: ExecutionTicket NOT ISSUED, execution
          attempt NOT CREATED, provider contacted zero times. Every run uses a new,
          non-frozen transaction — never used for model selection or calibration.
        </p>
        <button
          onClick={() => void runWhySemanticAi()}
          disabled={whySemanticBusy}
          data-testid="run-why-semantic-ai"
        >
          {whySemanticBusy ? "Running real engines…" : "Run WHY SEMANTIC AI MATTERS demo"}
        </button>
        {whySemantic && (
          <div data-testid="why-semantic-ai-result">
            <p>
              <strong>{whySemantic.label}</strong> · live engines · fresh non-frozen
              transaction per run
            </p>
            <table>
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody data-testid="why-semantic-ai-stages">
                <tr>
                  <td>Structured RazorGuard</td>
                  <td>
                    <strong>{whySemantic.structured_lane_detail.razorguard}</strong>
                  </td>
                </tr>
                {whySemantic.demonstration.map((row) => (
                  <tr key={row.pair_id}>
                    <td>Semantic Trust Check — {row.aspect}</td>
                    <td>
                      <strong>{row.semantic}</strong>
                    </td>
                  </tr>
                ))}
                <tr>
                  <td>Conservative Fusion</td>
                  <td>
                    <strong>{whySemantic.demonstration[0]?.fusion}</strong>
                  </td>
                </tr>
                <tr>
                  <td>ExecutionTicket</td>
                  <td>
                    <strong>{whySemantic.demonstration[0]?.ticket}</strong>
                  </td>
                </tr>
                <tr>
                  <td>Execution Attempt</td>
                  <td>
                    <strong>{whySemantic.demonstration[0]?.execution_attempt}</strong>
                  </td>
                </tr>
                <tr>
                  <td>Provider calls</td>
                  <td>
                    <strong>{whySemantic.demonstration[0]?.provider_calls}</strong>
                  </td>
                </tr>
              </tbody>
            </table>
            <p className="page-sub">{whySemantic.story}</p>
            <details>
              <summary>Advanced · engine details</summary>
              <p className="page-sub">
                Active semantic model <code>{whySemantic.runtime.model_id}</code> · policy{" "}
                <code>{whySemantic.runtime.policy_version}</code> · fixture{" "}
                <code>{whySemantic.fixture.provenance}</code> (non-frozen) · demo transaction{" "}
                <code>{whySemantic.fixture.demo_transaction.intent_id.slice(0, 20)}…</code> ·
                durable authority proof: tickets {whySemantic.authority_proof.tickets_before} →{" "}
                {whySemantic.authority_proof.tickets_after}, attempts{" "}
                {whySemantic.authority_proof.attempts_before} →{" "}
                {whySemantic.authority_proof.attempts_after}, provider calls{" "}
                {whySemantic.authority_proof.provider_calls_before} →{" "}
                {whySemantic.authority_proof.provider_calls_after}
              </p>
              <p className="page-sub">{whySemantic.structured_lane_detail.note}</p>
              <table>
                <thead>
                  <tr>
                    <th>Demo pair</th>
                    <th>RazorGuard</th>
                    <th>Semantic</th>
                    <th>p(contradiction)</th>
                    <th>Fusion</th>
                    <th>Ticket</th>
                    <th>Attempt</th>
                    <th>Provider</th>
                  </tr>
                </thead>
                <tbody>
                  {whySemantic.demonstration.map((row) => (
                    <tr key={`adv-${row.pair_id}`}>
                      <td>
                        <code>{row.pair_id}</code>
                      </td>
                      <td>{row.razorguard}</td>
                      <td>{row.semantic}</td>
                      <td>{row.probabilities.contradiction.toFixed(4)}</td>
                      <td>{row.fusion}</td>
                      <td>{row.ticket}</td>
                      <td>{row.execution_attempt}</td>
                      <td>{row.provider_calls}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </div>
        )}
      </div>

      {demo && (
        <div className="card" data-testid="demo-result">
          <h3>
            Result — {demo.scenario}: FINAL {demo.final_decision}
          </h3>
          <table>
            <tbody>
              <tr>
                <th scope="row">Protocol firewall</th>
                <td>
                  {demo.protocol_firewall}
                  {demo.protocol_firewall_reasons?.length
                    ? ` — ${demo.protocol_firewall_reasons.join(", ")}`
                    : ""}
                </td>
              </tr>
              <tr>
                <th scope="row">Deterministic RazorGuard</th>
                <td>{demo.razorguard_decision}</td>
              </tr>
              <tr>
                <th scope="row">Semantic verifier</th>
                <td>
                  {demo.semantic_verifier}
                  {demo.semantic_verifier !== "NOT_RUN" &&
                    ` — p(contradiction) ${demo.semantic_probabilities.contradiction.toFixed(
                      4,
                    )}, p(entailment) ${demo.semantic_probabilities.entailment.toFixed(4)}, p(neutral) ${demo.semantic_probabilities.neutral.toFixed(4)}`}
                  {demo.semantic_fail_closed ? " — FAIL-CLOSED" : ""}
                </td>
              </tr>
              <tr>
                <th scope="row">Final fused decision</th>
                <td>{demo.final_decision}</td>
              </tr>
              <tr>
                <th scope="row">ExecutionTicket issued</th>
                <td>{demo.ticket_issued ? "yes" : "no"}</td>
              </tr>
              <tr>
                <th scope="row">Razorpay contacted</th>
                <td>{demo.provider_contacted ? "yes" : "no"}</td>
              </tr>
            </tbody>
          </table>
          <p className="page-sub">
            The AI proposes. RazorGuard authorizes. The trusted executor executes — the semantic
            model can only tighten a decision; it never issues tickets and never contacts the
            provider.
          </p>
        </div>
      )}

      {run && (
        <>
          <div className="card" data-testid="lab-summary">
            <h3>
              Suite result: {run.passed}/{run.total} scenarios behaved as designed
            </h3>
          </div>

          <div className="card" data-testid="lab-results">
            <h3>Actual outcomes</h3>
            <table>
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Family</th>
                  <th>Actual outcome</th>
                  <th>As designed?</th>
                </tr>
              </thead>
              <tbody>
                {run.results.map((r) => (
                  <tr key={r.scenario_id}>
                    <td>{r.scenario_id}</td>
                    <td>{r.family}</td>
                    <td>
                      {r.actual}
                      {r.detail ? ` — ${r.detail}` : ""}
                    </td>
                    <td>{r.passed ? "yes" : "NO"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card" data-testid="lab-evidence">
            <h3>Evidence tail (hash-chained audit events)</h3>
            <ul>
              {run.evidence_tail.map((e) => (
                <li key={e.seq}>
                  #{e.seq} · {e.event_type} · {e.actor} · sha256:{e.hash_head}…
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
      </div>
    </section>
  );
}
