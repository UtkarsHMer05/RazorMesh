"use client";

/**
 * Phase-5 Protocol Playground (M046-M061).
 *
 * Primary interactive UX for the protocols surface: pick a transport, mutate
 * the packet, send it through the REAL gateway engines (firewall → IR →
 * commitment → consistency), and see the per-check results animate in order.
 *
 * Every result comes from the backend. Mutations are inputs only.
 * Thesis banner: "Protocol validity is not transaction authority."
 */

import { useCallback, useEffect, useState } from "react";
import styles from "./playground.module.css";

type ProtocolSlice = { id: string; label: string; version: string; transport: string };
type Mutation = { id: string; label: string };

type RunResult = {
  protocol: string;
  protocol_version: string;
  mutation: string;
  packet: {
    merchant: string;
    total_minor: number;
    currency: string;
    recurring: string;
    item_count: number;
  };
  checks: Record<
    string,
    { status: string; detail: string }
  >;
  ir: {
    schema: string;
    merchant: string;
    items: number;
    total_minor: number;
    currency: string;
    recurring: string;
  };
  commitment_head: string;
  consistency: string;
  authority_note: string;
};

type CrossView = {
  lanes: { protocol: string; label: string; version: string; consistency: string; total_minor: number; diverged: boolean }[];
  envelope_consistency: Record<string, string>;
  overall: string;
  commitment_head: string;
  note: string;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const fmtINR = (m: number) => `₹${(m / 100).toLocaleString("en-IN")}`;

const CHECK_ORDER = [
  ["schema_version", "Schema / version"],
  ["identity_signature", "Identity / signature"],
  ["replay_idempotency", "Replay / idempotency"],
  ["protocol_firewall", "Protocol firewall"],
  ["consistency", "Commitment consistency"],
] as const;

const FAIL_WORDS = new Set(["FAIL", "PROTOCOL_BLOCK", "MISMATCH", "BLOCK"]);

export function ProtocolPlayground() {
  const [protocols, setProtocols] = useState<ProtocolSlice[]>([]);
  const [mutations, setMutations] = useState<Mutation[]>([]);
  const [selected, setSelected] = useState("ucp");
  const [mutation, setMutation] = useState("none");
  const [result, setResult] = useState<RunResult | null>(null);
  const [revealedChecks, setRevealedChecks] = useState(0);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [cross, setCross] = useState<CrossView | null>(null);
  const [diverge, setDiverge] = useState<string | null>(null);
  const [busyCross, setBusyCross] = useState(false);

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const [p, m] = await Promise.all([
          fetch(`${API}/protocol-playground/protocols`),
          fetch(`${API}/protocol-playground/mutations`),
        ]);
        if (!ignore) {
          setProtocols((await p.json()).protocols ?? []);
          setMutations((await m.json()).mutations ?? []);
        }
      } catch (e) {
        if (!ignore) setError(String(e));
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const run = useCallback(async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    setRevealedChecks(0);
    try {
      const res = await fetch(`${API}/protocol-playground/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ protocol: selected, mutation }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? `run failed (${res.status})`);
      setResult(body as RunResult);
      // Reveal checks in real order for readability (UI pacing only — the
      // backend decision already exists; no fake waiting on outcomes).
      for (let i = 1; i <= CHECK_ORDER.length; i++) {
        window.setTimeout(() => setRevealedChecks(i), i * 260);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }, [selected, mutation]);

  const runCross = useCallback(async (d: string | null) => {
    setBusyCross(true);
    setError(null);
    try {
      const url = d ? `${API}/protocol-playground/cross?diverge=${d}` : `${API}/protocol-playground/cross`;
      const res = await fetch(url);
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? "cross view failed");
      setCross(body as CrossView);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusyCross(false);
    }
  }, []);

  // Initial cross-protocol view loads through a microtask boundary (no
  // synchronous setState inside the effect body).
  useEffect(() => {
    const t = window.setTimeout(() => void runCross(null), 0);
    return () => window.clearTimeout(t);
  }, [runCross]);

  const statusClass = (status: string) =>
    FAIL_WORDS.has(status)
      ? styles.checkFail
      : status.includes("PASS") || status === "MATCH"
        ? styles.checkPass
        : status === "CHALLENGE"
          ? styles.checkChallenge
          : styles.checkPending;

  return (
    <section className={styles.playground} data-testid="protocol-playground">
      <div className={styles.thesis} data-testid="protocol-thesis">
        <strong>PROTOCOL VALIDITY IS NOT TRANSACTION AUTHORITY.</strong> A packet can pass every
        protocol check and still be a purchase the human never authorized. Final authority is
        RazorGuard + the trusted executor.
      </div>

      <div className={styles.controls}>
        <div className={styles.controlGroup}>
          <h3>Transport</h3>
          <div className={styles.protocolChips} data-testid="protocol-selector">
            {protocols.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`${styles.chip} ${selected === p.id ? styles.chipSelected : ""}`}
                aria-pressed={selected === p.id}
                onClick={() => setSelected(p.id)}
                data-testid={`protocol-${p.id}`}
              >
                {p.label}
                <span className={styles.chipVersion}>{p.version}</span>
              </button>
            ))}
          </div>
        </div>

        <div className={styles.controlGroup}>
          <h3>Packet mutation</h3>
          <select
            className={styles.mutationSelect}
            value={mutation}
            onChange={(e) => setMutation(e.target.value)}
            data-testid="mutation-select"
            aria-label="Packet mutation"
          >
            {mutations.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={run}
          disabled={running}
          data-testid="send-packet"
        >
          {running ? "Sending…" : "Send through gateway"}
        </button>
      </div>

      {error && (
        <div className="card" role="alert" data-testid="playground-error">
          {error}
        </div>
      )}

      {result && (
        <div className={styles.resultPanel} data-testid="packet-result">
          <div className={styles.packetCard}>
            <h3>Packet</h3>
            <dl>
              <div>
                <dt>Protocol</dt>
                <dd>
                  {result.protocol.toUpperCase()} {result.protocol_version}
                </dd>
              </div>
              <div>
                <dt>Merchant</dt>
                <dd>{result.packet.merchant}</dd>
              </div>
              <div>
                <dt>Total</dt>
                <dd>
                  {fmtINR(result.packet.total_minor)} {result.packet.currency}
                </dd>
              </div>
              <div>
                <dt>Recurring</dt>
                <dd>{result.packet.recurring}</dd>
              </div>
              <div>
                <dt>Commitment</dt>
                <dd>
                  <code>{result.commitment_head}…</code>
                </dd>
              </div>
            </dl>
          </div>

          <ol className={styles.checksList} data-testid="gateway-checks">
            {CHECK_ORDER.map(([key, label], idx) => {
              const check = result.checks[key];
              const revealed = idx < revealedChecks;
              return (
                <li
                  key={key}
                  className={`${styles.checkRow} ${revealed ? statusClass(check?.status ?? "") : styles.checkPending}`}
                  data-check={key}
                  data-state={revealed ? (check?.status ?? "PENDING") : "WAIT"}
                >
                  <span className={styles.checkLabel}>{label}</span>
                  <span className={styles.checkStatus}>
                    {revealed ? check?.status : "…"}
                  </span>
                  <span className={styles.checkDetail}>{revealed ? check?.detail : ""}</span>
                </li>
              );
            })}
          </ol>

          <div className={styles.authorityBridge} data-testid="authority-bridge">
            <h4>What this means for money</h4>
            <p>{result.authority_note}</p>
            <p className="page-sub">
              Protocol PASS only admits the packet to RazorGuard — it never authorizes payment.
              Run Scenario C below to watch a protocol-valid packet die at the authority layer.
            </p>
          </div>
        </div>
      )}

      {/* Cross-protocol consistency */}
      <div className={styles.crossSection} data-testid="cross-protocol">
        <h3>Cross-protocol consistency</h3>
        <p className="page-sub">
          One semantic transaction, five protocol representations, one commerce commitment.
          Diverge one lane and watch the real consistency engine isolate it.
        </p>
        <div className={styles.crossControls}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setDiverge(null);
              void runCross(null);
            }}
            disabled={busyCross}
          >
            All lanes true
          </button>
          {cross?.lanes.map((lane) => (
            <button
              key={lane.protocol}
              type="button"
              className={`btn btn-secondary btn-sm ${diverge === lane.protocol ? styles.divergeSelected : ""}`}
              onClick={() => {
                setDiverge(lane.protocol);
                void runCross(lane.protocol);
              }}
              disabled={busyCross}
              data-testid={`diverge-${lane.protocol}`}
            >
              Diverge {lane.label}
            </button>
          ))}
        </div>

        {cross && (
          <div className={styles.lanesWrap}>
            <div className={styles.lanesGraph}>
              {cross.lanes.map((lane) => (
                <div
                  key={lane.protocol}
                  className={`${styles.lane} ${lane.consistency === "MISMATCH" ? styles.laneDiverged : styles.laneMatched}`}
                  data-testid={`lane-${lane.protocol}`}
                  data-state={lane.consistency}
                >
                  <span className={styles.laneName}>{lane.label}</span>
                  <span className={styles.laneArrow} aria-hidden="true">
                    ───
                  </span>
                  <span className={styles.laneStatus}>{lane.consistency}</span>
                </div>
              ))}
              <div className={styles.commitmentNode} data-testid="commitment-node">
                commerce-commitment-v1
                <br />
                <code>{cross.commitment_head}…</code>
              </div>
            </div>
            <p data-testid="cross-overall" className={cross.overall === "MATCH" ? styles.overallMatch : styles.overallMismatch}>
              {cross.overall} — {cross.note}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
