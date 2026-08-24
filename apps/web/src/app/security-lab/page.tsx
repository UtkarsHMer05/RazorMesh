"use client";

import { useCallback, useEffect, useState } from "react";

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

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function SecurityLabPage() {
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [run, setRun] = useState<LabRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadScenarios = useCallback(async () => {
    try {
      const res = await fetch(`${API}/security-lab/scenarios`);
      if (!res.ok) throw new Error(`scenarios ${res.status}`);
      setScenarios((await res.json()).scenarios);
    } catch (e) {
      setError(`Scenario catalog unavailable — is the API running? (${String(e)})`);
    }
  }, []);

  useEffect(() => {
    void loadScenarios();
  }, [loadScenarios]);

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
    </section>
  );
}
