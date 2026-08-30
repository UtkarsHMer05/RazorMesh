"use client";

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

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function SecurityLabPage() {
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [run, setRun] = useState<LabRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState<DemoEvidence | null>(null);
  const [demoBusy, setDemoBusy] = useState<string | null>(null);

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
