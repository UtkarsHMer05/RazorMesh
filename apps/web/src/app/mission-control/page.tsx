"use client";

/**
 * Phase-5 Mission Control (M101-M113) — the primary video page.
 *
 * One screen tells the whole story: the live transaction packet travels the
 * real pipeline (Human → Agent → Merchant → Protocol → Firewall → IR →
 * RazorGuard → Semantic → Fusion → Ticket → Razorpay → Audit), driven ONLY by
 * real backend events on the current trace. The control deck triggers real
 * flows; the evidence sidebar shows why each decision happened; presenter
 * mode enlarges for recording; playback replays recorded events read-only.
 *
 * No duplicate business logic: everything reads the same trace APIs every
 * other page uses. Outcomes never hardcoded.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useLiveTrace } from "@/lib/live-trace";
import { formatTransactionValue } from "@/lib/formatTransactionValue";
import styles from "./mission-control.module.css";

type StageNode = {
  id: string;
  label: string;
  role: string;
};

const PIPELINE: StageNode[] = [
  { id: "human", label: "Human mandate", role: "Authority" },
  { id: "agent", label: "Shopping Agent", role: "Proposes only" },
  { id: "merchant", label: "Merchant", role: "Offer (untrusted)" },
  { id: "protocol", label: "Protocol", role: "MCP·UCP·AP2·ACP·A2A" },
  { id: "firewall", label: "Protocol Firewall", role: "Adapter evidence gate" },
  { id: "ir", label: "AgentCommerceIR", role: "Canonical normalization + commitment" },
  { id: "razorguard", label: "RazorGuard", role: "Deterministic rules" },
  { id: "semantic", label: "Semantic Trust", role: "Advisory" },
  { id: "fusion", label: "Conservative Fusion", role: "Only tightens" },
  { id: "ticket", label: "Execution Ticket", role: "Single-use authority" },
  { id: "provider", label: "Razorpay", role: "Trusted executor only" },
  { id: "reconciliation", label: "Reconciliation", role: "Exactly-once" },
  { id: "audit", label: "Audit", role: "Tamper-evident" },
];

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const fmtINR = (m: number | null | undefined) =>
  m == null ? "—" : `₹${(m / 100).toLocaleString("en-IN")}`;

export default function MissionControlPage() {
  const { traceId, summary, events, setTraceId } = useLiveTrace({
    active: true,
    autoStop: false, // keep polling: the video page stays live
  });

  // Playback: replay recorded events with pacing (read-only by construction —
  // it only re-renders the already-fetched list).
  const [playIndex, setPlayIndex] = useState<number | null>(null);
  const [speed, setSpeed] = useState(1);
  const [presenter, setPresenter] = useState(false);
  // F012: DEMO PREFLIGHT — real lightweight readiness probes.
  const [preflight, setPreflight] = useState<{
    label: string;
    all_ready: boolean;
    checks: { component: string; ready: boolean; detail: string; environment?: string }[];
  } | null>(null);
  const [preflightBusy, setPreflightBusy] = useState(false);

  const runPreflight = useCallback(async (warmUp: boolean) => {
    setPreflightBusy(true);
    setPreflight(null);
    try {
      const res = await fetch(
        `${API}/mission-control/preflight${warmUp ? "?warm_up=true" : ""}`,
      );
      if (!res.ok) throw new Error("preflight failed");
      setPreflight(await res.json());
    } catch (e) {
      setStatus(String(e));
    } finally {
      setPreflightBusy(false);
    }
  }, []);
  const timerRef = useRef<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const displayed = useMemo(
    () => (playIndex === null ? events : events.slice(0, playIndex + 1)),
    [events, playIndex],
  );

  const startPlayback = useCallback(() => {
    if (events.length === 0) return;
    setPlayIndex(0);
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = window.setInterval(() => {
      setPlayIndex((idx) => {
        if (idx === null) return null;
        if (idx >= events.length - 1) {
          if (timerRef.current) window.clearInterval(timerRef.current);
          return idx; // stop at the end (real stopping point)
        }
        return idx + 1;
      });
    }, Math.max(250, 800 / speed));
  }, [events, speed]);

  useEffect(() => () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
  }, []);

  const stopPlayback = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    setPlayIndex(null);
  }, []);

  // Node states derive ONLY from displayed events (real evidence).
  const nodeStates = useMemo(() => {
    const byStage = new Map<string, { status: string; detail: string }>();
    for (const e of displayed) {
      byStage.set(e.stage, { status: e.status, detail: e.detail ?? "" });
    }
    // F008: FIREWALL + IR derive from REAL trace evidence, not decoration.
    // The full-evidence rejection event (stage=protocol) carries the real
    // firewall verdict in its evidence payload; the acceptance pipeline's IR
    // normalization produced the commitment the packet was judged against.
    const rejection = displayed.find(
      (e) => e.stage === "protocol" && e.status === "BLOCK",
    );
    const firewallVerdict =
      typeof rejection?.evidence?.firewall === "string"
        ? (rejection.evidence.firewall as string)
        : null;
    if (firewallVerdict) {
      byStage.set("firewall", {
        status: firewallVerdict,
        detail: "Protocol firewall verdict from the acceptance run evidence (adapter verification gate).",
      });
    }
    // The IR stage is proven by the packet having REACHED the decision stages:
    // normalization + commitment happened (the commitment the envelope
    // carries is the normalized IR's). Never marked DONE without a packet.
    const reachedDecision = displayed.some((e) =>
      ["razorguard", "semantic", "fusion", "ticket"].includes(e.stage),
    );
    if (reachedDecision) {
      byStage.set("ir", {
        status: "DONE",
        detail: "Packet normalized into the canonical AgentCommerceIR; commitment bound to the envelope.",
      });
    }
    return PIPELINE.map((node) => {
      const hit = byStage.get(node.id);
      return {
        ...node,
        status: hit?.status ?? "—",
        detail: hit?.detail ?? "",
        state:
          hit == null
            ? "pending"
            : hit.status === "BLOCK" || hit.status === "WITHHELD" || hit.status === "FAILED"
              ? "block"
              : hit.status === "ALLOW" || hit.status === "DONE" || hit.status === "ISSUED" || hit.status === "PASS" || hit.status === "PROTOCOL_PASS"
                ? "pass"
                : hit.status === "CHALLENGE"
                  ? "challenge"
                  : "active",
      };
    });
  }, [displayed]);

  const stoppedAt = useMemo(() => {
    // The packet's stopping point: the DECISION boundary where the block
    // happened (razorguard/semantic/fusion/ticket), never a later evidence
    // event. WITHHELD means the money stopped at the ticket stage.
    const order = ["razorguard", "semantic", "fusion", "ticket"];
    for (const stage of order) {
      const hit = displayed.find((e) => e.stage === stage && e.status === "BLOCK");
      if (hit) return stage;
    }
    const withheld = displayed.find((e) => e.status === "WITHHELD");
    return withheld ? withheld.stage : null;
  }, [displayed]);

  const runScenario = useCallback(
    async (kind: "b" | "c") => {
      setBusy(true);
      setStatus(null);
      try {
        const res = await fetch(
          kind === "b"
            ? `${API}/phase4/acceptance/demo/scenario-b-semantic-violation`
            : `${API}/phase4/acceptance/demo/scenario-c-protocol-valid-intent-invalid`,
          { method: "POST" },
        );
        const body = await res.json();
        if (!res.ok) throw new Error("scenario failed");
        // Bind the mission to the exact trace this run created: the demo
        // response carries its intent_id (audit evidence), and the trace
        // registry resolves it deterministically.
        const intentId = (body as { intent_id?: string }).intent_id;
        if (intentId && /^intent_[0-9A-HJKMNP-TV-Z]{26}$/.test(intentId)) {
          const trace = await fetch(`/api/trace/by-intent/${intentId}`).then((r) =>
            r.ok ? r.json() : null,
          );
          if (trace?.trace_id) setTraceId(trace.trace_id);
        }
        setStatus(
          `Scenario ${kind.toUpperCase()} ran: final ${body.final_decision ?? "—"}, provider contacted ${body.provider_contacted ? "yes" : "no"}.`,
        );
      } catch (e) {
        setStatus(String(e));
      } finally {
        setBusy(false);
      }
    },
    [setTraceId],
  );

  // G019: REAL control-deck actions on the CURRENT trace's transaction.
  const [txDiff, setTxDiff] = useState<
    { trace_id: string; diff: { field: string; authorized: unknown; current: unknown }[]; clean: boolean } | null
  >(null);

  const refreshCurrentTransaction = useCallback(async (id: string) => {
    try {
      const res = await fetch(`${API}/mission-control/current-transaction/${id}`);
      if (res.status === 409) {
        // The current trace's checkout has no immutable baseline yet (e.g.
        // a run created before this contract). Honest absence, never a
        // guessed diff.
        setTxDiff(null);
        return;
      }
      if (!res.ok) {
        setTxDiff(null);
        return;
      }
      setTxDiff(await res.json());
    } catch {
      setTxDiff(null); // diff is best-effort in the UI; backend is authority
    }
  }, []);

  useEffect(() => {
    // Microtask boundary: no synchronous setState inside the effect body
    // (react-compiler lint); the diff is re-derived after events settle.
    const t = window.setTimeout(() => {
      if (!traceId) {
        setTxDiff(null);
        return;
      }
      void refreshCurrentTransaction(traceId);
    }, 0);
    return () => window.clearTimeout(t);
  }, [traceId, events.length, refreshCurrentTransaction]);

  const actOnCurrent = useCallback(
    async (action: "mutate" | "revert" | "execute", kind?: string) => {
      if (!traceId) return;
      setBusy(true);
      setStatus(null);
      try {
        const res = await fetch(`${API}/mission-control/${action}-current`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ trace_id: traceId, kind: kind ?? action }),
        });
        const body = await res.json();
        if (!res.ok) throw new Error(body.detail?.detail ?? body.detail ?? `${action} failed`);
        if (action === "execute") {
          setStatus(
            `${body.outcome} — ${body.note}`,
          );
        } else {
          setStatus(
            `${body.label || action}: changed ${body.changed_fields?.join(", ") || "nothing"}. ${body.note ?? ""}`,
          );
        }
        await refreshCurrentTransaction(traceId);
      } catch (e) {
        setStatus(String(e));
      } finally {
        setBusy(false);
      }
    },
    [traceId, refreshCurrentTransaction],
  );

  const demoReset = useCallback(async () => {
    setBusy(true);
    setStatus(null);
    try {
      const res = await fetch(`${API}/mission-control/reset`, { method: "POST" });
      const body = await res.json();
      if (!res.ok) throw new Error("reset failed");
      setStatus(
        `Demo reset complete — ${body.surviving_traces} prior missions still searchable in Audit (history preserved).`,
      );
    } catch (e) {
      setStatus(String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  const nodeClass = (state: string) =>
    state === "block"
      ? styles.nodeBlock
      : state === "pass"
        ? styles.nodePass
        : state === "challenge"
          ? styles.nodeChallenge
          : state === "active"
            ? styles.nodeActive
            : styles.nodePending;

  return (
    <div className={`${styles.mc} ${presenter ? styles.presenter : ""}`}>
      <header className={styles.header}>
        <h1 className="page-title">Mission Control</h1>
        <p className="page-sub">
          One transaction, end to end. The packet moves only as far as the real evidence says —
          and never past a BLOCK.
          {traceId && (
            <>
              {" "}
              Live mission <strong>{traceId}</strong>
              {" "}
              <span className={styles.envBadge} data-testid="env-badge">
                {(() => {
                  const payment = preflight?.checks.find(
                    (c) => c.component === "Payment environment",
                  );
                  return payment?.environment ?? "…";
                })()}
              </span>
            </>
          )}
        </p>
        <div className={styles.modeControls}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            aria-pressed={presenter}
            onClick={() => setPresenter((v) => !v)}
            data-testid="presenter-mode"
          >
            {presenter ? "Exit presenter mode" : "Presenter mode"}
          </button>
          {presenter && <span className={styles.presenterBadge}>RECORDING VIEW</span>}
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => void runPreflight(false)}
            disabled={preflightBusy}
            data-testid="run-preflight"
          >
            {preflightBusy ? "Probing…" : "Run demo preflight"}
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => void runPreflight(true)}
            disabled={preflightBusy}
            data-testid="run-preflight-warmup"
            title="Same probes + a non-authoritative compiler warm-up request so the first real compile is fast"
          >
            Preflight + warm-up compiler
          </button>
        </div>
        {preflight && (
          <div className="card" data-testid="preflight-panel">
            <h3>
              {preflight.label} —{" "}
              {preflight.all_ready ? "ALL COMPONENTS READY" : "NOT READY — check failures"}
            </h3>
            <ul>
              {preflight.checks.map((c) => (
                <li key={c.component} data-testid={`preflight-${c.component.replace(/\s+/g, "-").toLowerCase()}`}>
                  {c.ready ? "✓" : "✗"} <strong>{c.component}</strong> — {c.detail}
                </li>
              ))}
            </ul>
            <p className="page-sub">
              Real lightweight probes only — no secrets exposed, no mandate compiled, nothing
              fabricated. The payment environment line states which environment traces execute
              in, so no local security mission is presented as a live provider transaction.
            </p>
          </div>
        )}
      </header>

      <div className={styles.layout}>
        {/* Pipeline graph (M102/M103) */}
        <section className={styles.pipeline} data-testid="mc-pipeline" aria-label="Live pipeline">
          {nodeStates.map((node, i) => (
            <div key={node.id} className={styles.pipelineCell}>
              <div
                className={`${styles.node} ${nodeClass(node.state)}`}
                data-testid={`node-${node.id}`}
                data-stage={node.id}
                data-state={node.status}
              >
                <span className={styles.nodeLabel}>{node.label}</span>
                <span className={styles.nodeRole}>{node.role}</span>
                <span className={styles.nodeStatus}>{node.status}</span>
                {node.detail && <span className={styles.nodeDetail}>{node.detail}</span>}
              </div>
              {i < nodeStates.length - 1 && (
                <div
                  className={`${styles.connector} ${
                    stoppedAt === node.id ? styles.connectorBroken : styles.connectorFlow
                  }`}
                  aria-hidden="true"
                >
                  {stoppedAt === node.id ? "✕" : "↓"}
                </div>
              )}
            </div>
          ))}
          {stoppedAt && (
            <p className={styles.stoppedAt} data-testid="stopped-at">
              The packet stopped at <strong>{stoppedAt}</strong> — exactly where the backend
              evidence says it stopped. Razorpay was never contacted.
            </p>
          )}
        </section>

        <aside className={styles.side}>
          {/* Evidence sidebar (M105) */}
          <section className={styles.evidence} data-testid="mc-evidence">
            <h2>Evidence</h2>
            <dl>
              <div>
                <dt>Trace</dt>
                <dd>{traceId ?? "no mission yet"}</dd>
              </div>
              <div>
                <dt>State</dt>
                <dd>{summary?.state ?? "—"}</dd>
              </div>
              <div>
                <dt>Final decision</dt>
                <dd>{summary?.final_decision ?? "—"}</dd>
              </div>
              <div>
                <dt>Ticket</dt>
                <dd>{summary?.ticket_state ?? "—"}</dd>
              </div>
              <div>
                <dt>Provider calls</dt>
                <dd>{summary?.provider_call_count ?? 0}</dd>
              </div>
              <div>
                <dt>Amount</dt>
                <dd>{fmtINR(summary?.amount_minor)}</dd>
              </div>
            </dl>
            <details className={styles.advanced}>
              <summary>Advanced · event log</summary>
              <ul>
                {displayed.map((e) => (
                  <li key={e.seq}>
                    <code>#{e.seq}</code> {e.stage}: {e.status}
                  </li>
                ))}
              </ul>
            </details>
            {summary?.intent_id && (
              <details className={styles.advanced}>
                <summary>Advanced · ids</summary>
                <code>intent: {summary.intent_id}</code>
              </details>
            )}
            {/* G020: current transaction diff (immutable baseline vs live) */}
            {txDiff && (
              <div className={styles.txDiff} data-testid="mc-tx-diff">
                <h3>Current transaction — authorized vs current</h3>
                {txDiff.clean ? (
                  <p className="page-sub" data-testid="mc-tx-clean">
                    No drift — the current transaction matches the immutable authorization
                    baseline exactly.
                  </p>
                ) : (
                  <table className={styles.diffTable} data-testid="mc-tx-diff-rows">
                    <thead>
                      <tr>
                        <th>Field</th>
                        <th>Authorized</th>
                        <th>Current</th>
                      </tr>
                    </thead>
                    <tbody>
                      {txDiff.diff.map((d) => (
                        <tr key={d.field}>
                          <td>{d.field}</td>
                          <td>{formatTransactionValue(d.field, d.authorized)}</td>
                          <td>
                            <strong>{formatTransactionValue(d.field, d.current)}</strong> ← CHANGED
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <p className="page-sub">
                  Authorized side = the immutable TransactionBaseline captured at proposal time
                  (a catalog change can never alter it). Current side = the live checkout row.
                </p>
              </div>
            )}
          </section>

          {/* Control deck (M104 + G019): real actions on the current trace */}
          <section className={styles.deck} data-testid="mc-controls">
            <h2>Control deck</h2>
            <p className="page-sub">
              Actions on the CURRENT mission&apos;s transaction (trace{" "}
              <strong>{traceId ?? "—"}</strong>) are labeled “on current”.
              Launching a NEW mission or navigating elsewhere is labeled as
              exactly that — never as a transaction action.
            </p>
            <div className={styles.deckGrid}>
              <Link className="btn btn-primary btn-sm" href="/buyer" data-testid="mc-safe">
                Open Buyer — launch new mission (navigate) →
              </Link>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void runScenario("b")}
                disabled={busy}
                data-testid="mc-hidden-membership"
              >
                Launch new Hidden-membership mission
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void runScenario("c")}
                disabled={busy}
                data-testid="mc-protocol-thesis"
              >
                Launch new Protocol-thesis mission
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void actOnCurrent("mutate", "price_drift")}
                disabled={busy || !traceId}
                data-testid="mc-mutate-price"
              >
                Price drift on current
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void actOnCurrent("mutate", "quantity_increase")}
                disabled={busy || !traceId}
                data-testid="mc-mutate-quantity"
              >
                Quantity +1 on current
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void actOnCurrent("mutate", "merchant_swap")}
                disabled={busy || !traceId}
                data-testid="mc-mutate-merchant"
              >
                Merchant swap on current
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void actOnCurrent("mutate", "hidden_membership")}
                disabled={busy || !traceId}
                data-testid="mc-mutate-hidden-recurring"
              >
                Hidden recurring on current
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void actOnCurrent("mutate", "protocol_mutation")}
                disabled={busy || !traceId}
                data-testid="mc-mutate-protocol"
              >
                Protocol mutation on current
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void actOnCurrent("execute")}
                disabled={busy || !traceId}
                data-testid="mc-execute-current"
              >
                Execute current transaction
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => void actOnCurrent("revert")}
                disabled={busy || !traceId}
                data-testid="mc-revert-current"
              >
                Revert current mutation
              </button>
              <Link className="btn btn-secondary btn-sm" href={traceId ? `/audit?trace=${traceId}` : "/audit"} data-testid="mc-open-audit">
                Open Audit (navigate) →
              </Link>
              <Link className="btn btn-secondary btn-sm" href="/protocols" data-testid="mc-open-protocols">
                Open Protocols (navigate) →
              </Link>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => void demoReset()}
                disabled={busy}
                data-testid="mc-demo-reset"
              >
                Clean demo reset
              </button>
            </div>
            {status && (
              <p className={styles.status} data-testid="mc-status" role="status">
                {status}
              </p>
            )}

            {/* Playback (M107): read-only replay of recorded events */}
            <div className={styles.playback} data-testid="mc-playback">
              <button type="button" className="btn btn-secondary btn-sm" onClick={startPlayback} disabled={events.length === 0}>
                Replay trace
              </button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={stopPlayback} disabled={playIndex === null}>
                Stop replay
              </button>
              <label className={styles.speedLabel}>
                Speed
                <select
                  value={speed}
                  onChange={(e) => setSpeed(Number(e.target.value))}
                  aria-label="Replay speed"
                >
                  <option value={0.5}>0.5×</option>
                  <option value={1}>1×</option>
                  <option value={2}>2×</option>
                </select>
              </label>
            </div>
          </section>

          {/* Campaign + governance summaries (M113/M114) */}
          <MissionSummaries />
        </aside>
      </div>
    </div>
  );
}

function MissionSummaries() {
  const [campaign, setCampaign] = useState<{
    total: number;
    safe_pass: number;
    attack_block: number;
    false_allows: number;
    false_blocks: number;
  } | null>(null);
  const [challenger, setChallenger] = useState<{
    verdict: string;
    human_gold: { macro_f1: { after: number } };
    normal_test_macro_f1: { after: number };
  } | null>(null);

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const [c, g] = await Promise.all([
          fetch(`${API}/security-campaign/summary`),
          fetch(`${API}/model-governance`),
        ]);
        if (!ignore) {
          setCampaign(await c.json());
          setChallenger((await g.json()).challenger);
        }
      } catch {
        // summaries are optional on this page
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section className={styles.summaries} data-testid="mc-summaries">
      <h2>Security breadth</h2>
      {campaign ? (
        <p>
          AgentPay-X canonical benchmark: <strong>{campaign.total}</strong> scenarios · safe
          pass <strong>{Math.round(campaign.safe_pass * 100)}%</strong> · attack block{" "}
          <strong>{Math.round(campaign.attack_block * 100)}%</strong> · false allows{" "}
          <strong>{campaign.false_allows}</strong> · false blocks{" "}
          <strong>{campaign.false_blocks}</strong>.
        </p>
      ) : (
        <p className="page-sub">Loading campaign summary…</p>
      )}
      {challenger && (
        <>
          <h2>Model governance</h2>
          <p>
            A higher-scoring challenger (test macro-F1{" "}
            {challenger.normal_test_macro_f1.after}) was <strong>REJECTED</strong> by the
            frozen safety gate ({challenger.verdict}) — human-gold macro-F1 regressed to{" "}
            {challenger.human_gold.macro_f1.after}. Safety ships over headline accuracy.{" "}
            <Link href="/governance">Details →</Link>
          </p>
        </>
      )}
    </section>
  );
}
