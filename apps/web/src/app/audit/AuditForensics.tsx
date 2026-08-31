"use client";

/**
 * Phase-5 Audit as Transaction Forensics (M079-M089).
 *
 * Primary UX: smart search (trace/intent/checkout ids), recent trace cards,
 * selected-trace dossier: visual timeline, authorization-vs-current diff,
 * provider-contact card, chain anchors, read-only replay. The raw event
 * wall remains available below as Raw Evidence / Developer View.
 *
 * All values come from backend evidence; chain verification uses the real
 * backend verifier; tamper simulation is the non-mutating one.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import styles from "./forensics.module.css";

type TraceSummary = {
  trace_id: string;
  intent_id: string;
  state: string;
  final_decision: string | null;
  provider_contacted: boolean;
  provider_call_count: number;
  amount_minor: number | null;
  updated_at: string;
};

type StageEvent = {
  seq: number;
  ts: string;
  stage: string;
  kind: string;
  title: string;
  status: string;
  detail: string | null;
  evidence: Record<string, unknown>;
};

type Dossier = {
  trace: TraceSummary;
  events: StageEvent[];
  diff: { field: string; authorized: unknown; current: unknown }[];
  provider: {
    contacted: boolean;
    call_count: number;
    order_id: string | null;
    attempt_state: string | null;
    reconcile_state: string | null;
  };
  chain?: {
    nodes: { seq: number; event_type: string; prev_head: string; hash_head: string }[];
    linked: boolean;
    node_count: number;
    note: string;
  };
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const fmtINR = (m: unknown) =>
  typeof m === "number" ? `₹${(m / 100).toLocaleString("en-IN")}` : "—";

const STAGE_ICONS: Record<string, string> = {
  human: "●",
  agent: "●",
  merchant: "▲",
  protocol: "■",
  razorguard: "■",
  semantic: "◆",
  fusion: "◆",
  ticket: "★",
  provider: "▶",
  reconciliation: "▶",
  audit: "≡",
  replay: "↻",
};

export function AuditForensics() {
  const [query, setQuery] = useState("");
  const [recent, setRecent] = useState<TraceSummary[]>([]);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null);
  const [chain, setChain] = useState<{ valid: boolean; events_checked: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // G022: real read-only timeline playback. The player re-renders the
  // ALREADY-FETCHED events with pacing — it never re-executes anything,
  // never creates tickets/provider calls, and never appends audit rows
  // (proven by the G022 e2e count checks).
  const [playIndex, setPlayIndex] = useState<number | null>(null);
  const [playSpeed, setPlaySpeed] = useState(1);
  const timerRef = useRef<number | null>(null);

  const startPlayback = useCallback(() => {
    if (!dossier || dossier.events.length === 0) return;
    setPlayIndex(0);
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = window.setInterval(() => {
      setPlayIndex((idx) => {
        if (idx === null) return null;
        if (idx >= dossier.events.length - 1) {
          if (timerRef.current) window.clearInterval(timerRef.current);
          return idx;
        }
        return idx + 1;
      });
    }, Math.max(250, 900 / playSpeed));
  }, [dossier, playSpeed]);

  const pausePlayback = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current);
  }, []);

  const resetPlayback = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    setPlayIndex(null);
  }, []);

  useEffect(
    () => () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    },
    [],
  );

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const res = await fetch(`${API}/forensics/recent`);
        if (!ignore) setRecent((await res.json()).traces ?? []);
      } catch (e) {
        if (!ignore) setError(String(e));
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);


  const loadDossier = useCallback(async (traceId: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/forensics/trace/${traceId}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? "trace lookup failed");
      if (timerRef.current) window.clearInterval(timerRef.current);
      setPlayIndex(null);
      setDossier(body as Dossier);
      setSelectedTrace(traceId);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, []);

// Deep link (M016/M089): ?trace=RM-XXXXXX auto-opens the dossier — the
  // judge lands on the forensics for the exact mission they followed here.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const param = new URLSearchParams(window.location.search).get("trace");
    if (param && /^RM-[0-9A-HJKMNP-TV-Z]{6}$/.test(param)) {
      const t = window.setTimeout(() => void loadDossier(param), 0);
      return () => window.clearTimeout(t);
    }
  }, [loadDossier]);

    const search = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/forensics/search?q=${encodeURIComponent(q)}`);
      const body = await res.json();
      if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "not found");
      await loadDossier(body.match.trace_id);
    } catch (e) {
      setError(`${e instanceof Error ? e.message : String(e)} — try a trace id like the recent cards below.`);
    } finally {
      setBusy(false);
    }
  }, [query, loadDossier]);

  const verifyChain = useCallback(async () => {
    setBusy(true);
    try {
      const res = await fetch(`${API}/audit/verify`);
      const body = await res.json();
      setChain({ valid: Boolean(body.valid), events_checked: body.events_checked });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  const stateBadge = (s: string) =>
    s === "BLOCK" || s === "WITHHELD" || s === "FAILED"
      ? styles.badgeBlock
      : s === "ALLOW" || s === "ISSUED" || s === "EXECUTING"
        ? styles.badgeAllow
        : styles.badgeNeutral;

  const timeline = useMemo(
    () =>
      playIndex === null
        ? (dossier?.events ?? [])
        : (dossier?.events ?? []).slice(0, playIndex + 1),
    [dossier, playIndex],
  );
  const currentEvent =
    playIndex !== null && dossier ? dossier.events[playIndex] : null;

  return (
    <div className={styles.forensics} data-testid="audit-forensics">
      {/* Smart search (M080) */}
      <div className={styles.searchRow} data-testid="forensics-search">
        <label htmlFor="forensics-q" className="field-label">
          Search trace / intent / checkout
        </label>
        <div className={styles.searchBar}>
          <input
            id="forensics-q"
            className={styles.searchInput}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="RM-84C91A or intent_… or chk_…"
            onKeyDown={(e) => e.key === "Enter" && void search()}
          />
          <button type="button" className="btn btn-primary btn-sm" onClick={() => void search()} disabled={busy}>
            Search
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => void verifyChain()} disabled={busy}>
            Verify hash chain
          </button>
        </div>
        {chain && (
          <p className={chain.valid ? styles.chainValid : styles.chainBroken} data-testid="chain-status">
            {chain.valid ? "CHAIN VALID" : "CHAIN BROKEN"} over {chain.events_checked} events
            (backend verifier)
          </p>
        )}
      </div>

      {error && (
        <div className="card" role="alert" data-testid="forensics-error">
          {error}
        </div>
      )}

      {/* Recent trace cards (M081) */}
      <section className={styles.recentSection} data-testid="recent-traces">
        <h3>Recent missions</h3>
        {recent.length === 0 ? (
          <p className="page-sub">No traces yet — run a mission on the Buyer page.</p>
        ) : (
          <div className={styles.recentGrid}>
            {recent.map((t) => (
              <button
                key={t.trace_id}
                type="button"
                className={`${styles.recentCard} ${selectedTrace === t.trace_id ? styles.recentSelected : ""}`}
                onClick={() => void loadDossier(t.trace_id)}
                data-testid={`recent-${t.trace_id}`}
              >
                <strong className={styles.recentId}>{t.trace_id}</strong>
                <span className={`${styles.recentState} ${stateBadge(t.final_decision ?? t.state)}`}>
                  {t.final_decision ?? t.state}
                </span>
                <span>
                  {t.provider_contacted ? `provider ${t.provider_call_count}×` : "provider 0"}
                  {t.amount_minor ? ` · ${fmtINR(t.amount_minor)}` : ""}
                </span>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Dossier (M082-M085) */}
      {dossier && (
        <section className={styles.dossier} data-testid="forensic-dossier">
          <h3>
            Forensics — <strong>{dossier.trace.trace_id}</strong>
          </h3>

          <div className={styles.dossierGrid}>
            {/* Visual timeline */}
            <div className={styles.timelineCard}>
              <h4>Transaction timeline</h4>
              {timeline.length === 0 ? (
                <p className="page-sub">No projected events for this trace yet.</p>
              ) : (
                <ol className={styles.timeline} data-testid="forensic-timeline">
                  {timeline.map((e) => (
                    <li
                      key={e.seq}
                      className={styles.timelineRow}
                      data-stage={e.stage}
                      data-state={e.status}
                    >
                      <span className={styles.tlTime}>
                        {new Date(e.ts).toLocaleTimeString("en-IN", { hour12: false })}
                      </span>
                      <span className={styles.tlIcon} aria-hidden="true">
                        {STAGE_ICONS[e.stage] ?? "·"}
                      </span>
                      <span className={styles.tlTitle}>{e.title}</span>
                      <span className={`${styles.tlStatus} ${stateBadge(e.status)}`}>{e.status}</span>
                      {e.detail && <span className={styles.tlDetail}>{e.detail}</span>}
                    </li>
                  ))}
                </ol>
              )}
            </div>

            <div className={styles.sideCards}>
              {/* Authorization-vs-current diff */}
              <div className={styles.diffCard} data-testid="auth-exec-diff">
                <h4>Authorization vs current</h4>
                {dossier.diff.length === 0 ? (
                  <p className="page-sub">No drift — execution state matches the mandate.</p>
                ) : (
                  <table className={styles.diffTable}>
                    <thead>
                      <tr>
                        <th>Field</th>
                        <th>Authorized</th>
                        <th>Current</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dossier.diff.map((d) => (
                        <tr key={d.field}>
                          <td>{d.field}</td>
                          <td>{fmtINR(d.authorized) === "—" ? "—" : fmtINR(d.authorized)}</td>
                          <td>
                            <strong>{fmtINR(d.current) === "—" ? JSON.stringify(d.current) : fmtINR(d.current)}</strong>{" "}
                            ← CHANGED
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Provider-contact card */}
              <div className={styles.providerCard} data-testid="provider-card">
                <h4>Provider contact</h4>
                <dl>
                  <div>
                    <dt>Contacted</dt>
                    <dd>{dossier.provider.contacted ? "YES" : "NO"}</dd>
                  </div>
                  <div>
                    <dt>Provider calls</dt>
                    <dd>{dossier.provider.call_count}</dd>
                  </div>
                  <div>
                    <dt>Order id</dt>
                    <dd>
                      <code>{dossier.provider.order_id ?? "—"}</code>
                    </dd>
                  </div>
                  <div>
                    <dt>Attempt</dt>
                    <dd>{dossier.provider.attempt_state ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>Reconciliation</dt>
                    <dd>{dossier.provider.reconcile_state ?? "—"}</dd>
                  </div>
                </dl>
                <p className="page-sub">
                  Order creation ≠ payment success; this card reports audit evidence only.
                </p>
              </div>

              {/* Handoff (M089) */}
              <div className={styles.handoffCard}>
                <h4>Follow this trace</h4>
                <div className={styles.handoffLinks}>
                  {[
                    ["/buyer", "Buyer"],
                    ["/merchant", "Merchant"],
                    ["/protocols", "Protocols"],
                    ["/security-lab", "Security Lab"],
                  ].map(([route, label]) => (
                    <Link
                      key={route}
                      className="btn btn-secondary btn-sm"
                      href={`${route}?trace=${dossier.trace.trace_id}`}
                    >
                      {label} →
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* G022: REAL read-only timeline playback over the stored events */}
          <div className={styles.replayPlayer} data-testid="forensic-replay">
            <h4>Replay this transaction (read-only playback)</h4>
            <div className={styles.playbackControls}>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={startPlayback}
                disabled={dossier.events.length === 0}
                data-testid="replay-play"
              >
                ▶ Play
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={pausePlayback}
                disabled={playIndex === null}
                data-testid="replay-pause"
              >
                ⏸ Pause
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={resetPlayback}
                disabled={playIndex === null}
                data-testid="replay-reset"
              >
                ⟲ Reset
              </button>
              <label className={styles.speedLabel}>
                Speed
                <select
                  value={playSpeed}
                  onChange={(e) => setPlaySpeed(Number(e.target.value))}
                  aria-label="Playback speed"
                  data-testid="replay-speed"
                >
                  <option value={0.5}>0.5×</option>
                  <option value={1}>1×</option>
                  <option value={2}>2×</option>
                </select>
              </label>
              <span className={styles.playPosition} data-testid="replay-position">
                {playIndex === null
                  ? `${dossier.events.length} events`
                  : `${playIndex + 1} / ${dossier.events.length}`}
              </span>
            </div>
            {currentEvent && (
              <p className={styles.currentEvent} data-testid="replay-current">
                <strong>
                  #{currentEvent.seq} {currentEvent.title}
                </strong>{" "}
                — {currentEvent.status}
              </p>
            )}
            <p className="page-sub">
              Playback re-renders the stored audit events only. It never re-executes the
              pipeline: no new tickets, no provider calls, no new audit entries — the
              provider-call count and event count are unchanged after any replay.
            </p>
          </div>

          {/* G023: the SELECTED trace's own hash-chain nodes */}
          {dossier.chain && dossier.chain.nodes.length > 0 && (
            <div className={styles.chainView} data-testid="trace-chain">
              <h4>
                This trace&apos;s hash chain ({dossier.chain.node_count} events{" "}
                {dossier.chain.linked ? "· LINKED" : "· LINK BROKEN"})
              </h4>
              <p className="page-sub">
                Each event&apos;s hash covers the previous event. Change any row and every
                later link in THIS trace breaks — that is where tamper would be caught.
                Global ledger verification is a separate action above.
              </p>
              <ol className={styles.chainNodes} data-testid="chain-nodes">
                {dossier.chain.nodes.map((n, i) => (
                  <li
                    key={n.seq}
                    className={`${styles.chainNode} ${
                      currentEvent && currentEvent.seq === n.seq ? styles.chainNodeCurrent : ""
                    }`}
                    data-seq={n.seq}
                    data-testid={`chain-node-${n.seq}`}
                  >
                    <code>#{n.seq}</code>{" "}
                    <span className={styles.chainEventType}>{n.event_type}</span>
                    <span className={styles.chainHash} title="hash head">
                      {n.hash_head}…
                    </span>
                    {i > 0 && (
                      <span className={styles.chainLink} title="linked to previous">
                        ← {n.prev_head}…
                      </span>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
