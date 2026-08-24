"use client";

import { useCallback, useEffect, useState } from "react";

type AuditEvent = {
  seq: number;
  event_id: string;
  event_type: string;
  actor: string;
  timestamp: string;
  intent_id: string | null;
  reason_codes: string[];
  previous_event_hash_head: string;
  current_event_hash_head: string;
};

type VerifyBody = {
  valid: boolean;
  events_checked: number;
  broken_at_event_id: string | null;
  reason: string | null;
};

type Spend = {
  authorized_minor: number;
  reserved_minor: number;
  committed_minor: number;
  available_minor: number;
} | null;

type IntentState = {
  intent_id: string;
  status: string;
  generation: number;
  spend: Spend;
  decisions: { decision_id: string; decision: string; policy_version: string; reason_codes: string[] }[];
  tickets: { ticket_id: string; nonce_present: boolean; amount_minor: number; used_at: string | null }[];
  attempts: { attempt_id: string; state: string; error_code: string | null }[];
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [verify, setVerify] = useState<VerifyBody | null>(null);
  const [intentId, setIntentId] = useState("");
  const [state, setState] = useState<IntentState | null>(null);
  const [tamper, setTamper] = useState<{ detected: boolean; verdict_reason: string | null } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  const loadTimeline = useCallback(async () => {
    try {
      const res = await fetch(`${API}/audit/timeline?limit=50`);
      if (!res.ok) throw new Error(`timeline ${res.status}`);
      setEvents((await res.json()).events);
    } catch (e) {
      setError(`Audit API unavailable — is the backend running? (${String(e)})`);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const res = await fetch(`${API}/audit/timeline?limit=50`);
        if (!res.ok) throw new Error(`timeline ${res.status}`);
        const body = await res.json();
        if (!ignore) setEvents(body.events);
      } catch (e) {
        if (!ignore) setError(`Audit API unavailable — is the backend running? (${String(e)})`);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const verifyChain = async () => {
    setError(null);
    try {
      const res = await fetch(`${API}/audit/verify`);
      setVerify(await res.json());
    } catch (e) {
      setError(String(e));
    }
  };

  const loadState = async () => {
    setError(null);
    try {
      const res = await fetch(`${API}/audit/state/${intentId}`);
      if (!res.ok) throw new Error(`state ${res.status}`);
      setState(await res.json());
    } catch (e) {
      setError(String(e));
    }
  };

  const runTamperTest = async () => {
    setError(null);
    try {
      const res = await fetch(`${API}/audit/tamper-test`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      setTamper(await res.json());
      await loadTimeline();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <section aria-labelledby="audit-title">
      <h1 className="page-title" id="audit-title">
        Audit dashboard
      </h1>
      <p className="page-sub">
        Chronological evidence timeline with hashes and reason codes, reservation/execution
        state inspector, chain verification, and a visible tamper test. UI reflects stored
        evidence only.
      </p>

      {error && (
        <div className="card" role="alert" data-testid="audit-error">
          {error}
        </div>
      )}

      <div className="card" data-testid="audit-controls">
        <button onClick={loadTimeline}>Refresh timeline</button>{" "}
        <button onClick={verifyChain}>Verify hash chain</button>{" "}
        <button onClick={runTamperTest}>Run non-mutating tamper simulation</button>
        {verify && (
          <p data-testid="verify-result">
            Chain {verify.valid ? "VALID" : "BROKEN"} over {verify.events_checked} events
            {verify.broken_at_event_id ? ` — broken at ${verify.broken_at_event_id}` : ""}
            {verify.reason ? ` (${verify.reason})` : ""}
          </p>
        )}
        {tamper && (
          <p data-testid="tamper-result">
            Tamper simulation: {tamper.detected ? "DETECTED by chain verification" : "NOT DETECTED"}
            {tamper.verdict_reason ? ` — ${tamper.verdict_reason}` : ""} (ledger unchanged)
          </p>
        )}
      </div>

      <div className="card" data-testid="intent-inspector">
        <h3>Authorization / execution state</h3>
        <label>
          Intent ID{" "}
          <input
            value={intentId}
            onChange={(e) => setIntentId(e.target.value)}
            placeholder="intent_…"
            style={{ width: "22rem" }}
          />
        </label>{" "}
        <button onClick={loadState} disabled={!intentId}>
          Inspect
        </button>
        {state && (
          <div>
            <p>
              Status <strong>{state.status}</strong> · generation {state.generation}
              {state.spend && (
                <>
                  {" "}
                  · authorized {state.spend.authorized_minor} · reserved{" "}
                  {state.spend.reserved_minor} · committed {state.spend.committed_minor} ·
                  available {state.spend.available_minor}
                </>
              )}
            </p>
            <ul>
              {state.decisions.map((d) => (
                <li key={d.decision_id}>
                  Decision {d.decision} ({d.policy_version}) {d.reason_codes.join(", ")}
                </li>
              ))}
              {state.tickets.map((t) => (
                <li key={t.ticket_id}>
                  Ticket {t.ticket_id} — nonce present: {String(t.nonce_present)}, amount{" "}
                  {t.amount_minor}, used: {t.used_at ?? "never"}
                </li>
              ))}
              {state.attempts.map((a) => (
                <li key={a.attempt_id}>
                  Attempt {a.attempt_id} — {a.state}
                  {a.error_code ? ` (${a.error_code})` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="card" data-testid="audit-timeline">
        <h3>Evidence timeline ({events.length} events)</h3>
        <ol reversed>
          {[...events].reverse().map((e) => (
            <li key={e.event_id}>
              #{e.seq} · <strong>{e.event_type}</strong> · {e.actor} · sha256:
              {e.current_event_hash_head}…
              {e.intent_id && <> · intent {e.intent_id}</>}
              {e.reason_codes.length > 0 && <> · codes: {e.reason_codes.join(", ")}</>}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
