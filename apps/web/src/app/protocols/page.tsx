"use client";

/**
 * Phase-4 Protocol Gateway dashboard (M48).
 *
 * Uses the redesigned Bauhaus visual system (Outfit + Inter, primary
 * colors, hard borders, hard shadows). The page surfaces:
 *   - Protocol envelope inspector
 *   - AgentCommerceIR inspector
 *   - Cross-protocol consistency matrix
 *   - Signature / mandate verification state
 *   - Firewall / RazorGuard / NLI / final decision
 *   - AgentPay-X results
 *   - Audit links
 *
 * All data shown is local / fixture-based. The page never receives a
 * raw payment credential. It calls the same Phase-4 primitives that
 * the live protocol gateway uses; the values displayed are loaded
 * from a typed fixture client.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type {
  ProtocolEnvelope,
  AgentCommerceIR,
  ConsistencyState,
  FirewallDecision,
  AgentPayXResult,
} from "./types";

type GatewaySnapshot = {
  envelope: ProtocolEnvelope;
  ir: AgentCommerceIR;
  consistency: ConsistencyState;
  firewall: FirewallDecision;
  razorGuard: "ALLOW" | "CHALLENGE" | "BLOCK";
  final: "ALLOW" | "CHALLENGE" | "BLOCK";
  agentPayX: AgentPayXResult[];
  auditReceiptHref: string;
};

type LiveAcceptanceRun = {
  run_id: string;
  intent_id: string;
  checkout_id: string;
  idempotency_key: string;
  amount_minor: number;
  currency: string;
  completed: boolean;
  used_at: string | null;
  evidence: {
    mcp: {
      version: string;
      endpoint: string;
      method_tool: string;
      message_id: string;
    };
    ucp: {
      version: string;
      profile_path: string;
      signature_digest_verified: boolean;
      idempotency_key: string;
      commerce_evidence_hash: string;
    };
    ap2: {
      version: string;
      evidence_type: string;
      signature_verified: boolean;
      vct: string;
      expires_at: string;
      checkout_hash_binding: boolean;
      key_binding_pop_verified: boolean;
      evidence_hash: string;
    };
    razormesh: {
      intent_hash: string;
      protocol_firewall: string;
      protocol_firewall_reasons: string[];
      protocol_envelope_hash: string;
      agent_commerce_ir_hash: string;
      commerce_commitment: string;
      commerce_commitment_version: string;
      cross_protocol_consistency: string;
      razorguard_decision: string;
      semantic_verifier: string;
      final_decision: string;
      decided_at: string;
      // Semantic runtime truth (acceptance evidence §21). Optional: runs
      // recorded by older builds may omit them — render defensively as "—".
      semantic_backend?: string;
      semantic_model_version?: string;
      semantic_pair_count?: number;
      semantic_probabilities?: number[];
      semantic_fail_closed?: boolean;
    };
  };
};

// Rendered from the HTTP 409 body of POST /phase4/acceptance/prepare. The
// richer stage fields are additive on the backend: when absent, the card
// shows an em dash instead of inventing data.
type RejectionCard = {
  stage: string;
  reason: string;
  firewallStatus: string;
  razorGuardDecision: string;
  semanticAction: string;
  semanticProbabilities: number[] | null;
  finalDecision: string;
};

const FIXTURE_SNAPSHOT: GatewaySnapshot = {
  envelope: {
    schemaVersion: "protocol-envelope-v1",
    sourceProtocol: "ucp",
    sourceProtocolVersion: "2026-04-08",
    sourceTransport: "rest",
    adapterVersion: "razormesh-ucp-adapter-0.1.0",
    messageId: "msg_ucp_01",
    requestId: "req_ucp_01",
    idempotencyKey: "idem_ucp_01",
    rawPayloadHash: "0".repeat(64),
    signatureEvidence: { scheme: "ed25519", kid: "k_ucp_test" },
    identityEvidence: { agent: "untrusted_test_agent", principal: "principal_test" },
    capabilityEvidence: {
      profile: "2026-04-08",
      handlers: ["io.razormesh.razorpay.test_checkout"],
    },
    agent: "untrusted_test_agent",
    principalReference: "principal_test",
    merchantReference: "merch_synthaudio",
    commercePayloadReference: "ref_bose_quietcomfort_earbuds",
    authorizationEvidence: [],
    extensionEvidence: [{ uri: "https://razormesh.dev/extensions/ucp/v1" }],
    verificationState: "cross_protocol_checked",
    verificationReasons: [],
  },
  ir: {
    schemaVersion: "agent-commerce-ir-v1",
    principalRef: "principal_test",
    agentRef: "untrusted_test_agent",
    merchant: { merchantId: "merch_synthaudio" },
    checkout: { revision: "r-ucp-1" },
    items: [
      {
        productId: "prod_bose_quietcomfort_earbuds",
        quantity: { value: 1, unit: "EA", scale: 0 },
        unitPrice: { valueMinor: 189900, currency: "INR" },
        brand: "Bose",
        condition: "new",
      },
    ],
    totals: { totalMinor: 189900 },
    currency: "INR",
    recurring: { mode: "none" },
    authorization: {
      intentContractId: "ic_test_1",
      authorizationGeneration: 1,
    },
    provenance: { sourceProtocols: ["ucp", "ap2", "mcp", "a2a"] },
  },
  consistency: "MATCH",
  firewall: "PROTOCOL_PASS",
  razorGuard: "ALLOW",
  final: "ALLOW",
  agentPayX: [
    { name: "amount.plus-one", family: "amount_mutation", safe: false, expectedBlock: true, passed: true, reason: "MISMATCH" },
    { name: "merchant.substitution", family: "merchant_substitution", safe: false, expectedBlock: true, passed: true, reason: "MISMATCH" },
    { name: "recurring.inserted", family: "recurring_term_insertion", safe: false, expectedBlock: true, passed: true, reason: "MISMATCH" },
    { name: "mcp.downgrade", family: "mcp_protocol_downgrade", safe: false, expectedBlock: true, passed: true, reason: "PROTOCOL_BLOCK" },
    { name: "ap2.unknown_vct", family: "ap2_unknown_constraint", safe: false, expectedBlock: true, passed: true, reason: "vct_mismatch" },
    { name: "acp.illegal_transition", family: "acp_illegal_lifecycle_transition", safe: false, expectedBlock: true, passed: true, reason: "illegal_transition_blocked" },
    { name: "equivalent.canonical", family: "equivalent_representation", safe: true, expectedBlock: false, passed: true, reason: "MATCH" },
  ],
  auditReceiptHref: "/audit",
};

function Pill({ tone, children }: { tone: "allow" | "challenge" | "block"; children: React.ReactNode }) {
  const cls =
    tone === "allow" ? "pill pill--allow" : tone === "challenge" ? "pill pill--challenge" : "pill pill--block";
  return <span className={cls}>{children}</span>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="gateway-field">
      <span className="gateway-field__label">{label}</span>
      <span className="gateway-field__value">{children}</span>
    </div>
  );
}

function RunRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{children}</td>
    </tr>
  );
}

function Section({ eyebrow, title, children }: { eyebrow: string; title: string; children: React.ReactNode }) {
  return (
    <section className="landing-section landing-section--alt-white">
      <div className="container">
        <span className="eyebrow">{eyebrow}</span>
        <h2 className="section-heading">{title}</h2>
        {children}
      </div>
    </section>
  );
}

function dashIfEmpty(value: string | null | undefined): string {
  return value && value.trim().length > 0 ? value : "—";
}

function fmtProb(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "—";
}

function decisionTone(decision: string | null | undefined): "allow" | "challenge" | "block" {
  if (decision === "BLOCK") return "block";
  if (decision === "CHALLENGE") return "challenge";
  return "allow";
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function asProbabilityArray(value: unknown): number[] | null {
  if (!Array.isArray(value) || value.length !== 3) return null;
  return value.every((v) => typeof v === "number" && Number.isFinite(v))
    ? (value as number[])
    : null;
}

// The prepare route answers a rejection with HTTP 409 and a JSON body of the
// shape `{detail: {...}}`. `rejection_stage` is authoritative when present;
// `code`/`reason` are the legacy fallbacks. Backend rejection fields are
// additive — anything missing renders as "—".
function parseRejection(body: unknown): RejectionCard | null {
  if (typeof body !== "object" || body === null) return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail !== "object" || detail === null) return null;
  const d = detail as Record<string, unknown>;
  const stage = asString(d.rejection_stage) ?? asString(d.code);
  if (!stage) return null;
  return {
    stage,
    reason: asString(d.rejection_reason) ?? asString(d.reason) ?? "—",
    firewallStatus: asString(d.firewall_status) ?? "—",
    razorGuardDecision: asString(d.razorguard_decision) ?? "—",
    semanticAction: asString(d.semantic_action) ?? "—",
    semanticProbabilities: asProbabilityArray(d.semantic_probabilities),
    finalDecision: asString(d.final_decision) ?? "—",
  };
}

// Backend semantic_probabilities order is (p_contradiction, p_entailment,
// p_neutral); the UI always labels the values explicitly.
function semanticDetailSubLine(rm: NonNullable<LiveAcceptanceRun["evidence"]["razormesh"]>): string {
  const probs = Array.isArray(rm.semantic_probabilities) ? rm.semantic_probabilities : undefined;
  const parts: string[] = [
    `p(entail) ${fmtProb(probs?.[1])}`,
    `p(neutral) ${fmtProb(probs?.[2])}`,
    `p(contra) ${fmtProb(probs?.[0])}`,
  ];
  if (typeof rm.semantic_pair_count === "number" && rm.semantic_pair_count > 0) {
    parts.push(`${rm.semantic_pair_count} pairs`);
  }
  if (rm.semantic_backend) parts.push(`backend ${rm.semantic_backend}`);
  if (rm.semantic_model_version) parts.push(`model ${rm.semantic_model_version}`);
  if (rm.semantic_fail_closed) parts.push("FAIL-CLOSED");
  return parts.join(" · ");
}

export default function ProtocolGatewayPage() {
  const [snapshot] = useState<GatewaySnapshot>(() => FIXTURE_SNAPSHOT);
  const [liveRuns, setLiveRuns] = useState<LiveAcceptanceRun[] | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const [rejection, setRejection] = useState<RejectionCard | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [finalizingId, setFinalizingId] = useState<string | null>(null);

  // Phase-4 live-ingress closure: fetch the real acceptance-run
  // registry from the backend so the dashboard reflects the actual
  // MCP->UCP->AP2->Firewall->IR->Consistency->RazorGuard->ALLOW
  // artifacts produced during the live request, not just static proof
  // harness results.
  const fetchRuns = useCallback(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/phase4/acceptance/runs", { cache: "no-store" });
        if (!res.ok) {
          throw new Error(`http_${res.status}`);
        }
        const body = (await res.json()) as { runs?: LiveAcceptanceRun[] };
        if (!cancelled) {
          setLiveRuns(body.runs ?? []);
          setLiveError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setLiveError(err instanceof Error ? err.message : "fetch_failed");
          setLiveRuns([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return fetchRuns();
  }, [fetchRuns]);

  // Trigger a live acceptance run: fixture intent -> catalog product -> prepare.
  const triggerLiveRun = useCallback(async () => {
    setIsTriggering(true);
    setTriggerError(null);
    setRejection(null);
    try {
      const intentRes = await fetch("/api/buyer/fixture-intent", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "{}",
      });
      if (!intentRes.ok) throw new Error(`fixture_intent_${intentRes.status}`);
      const intentBody = await intentRes.json();
      const intentId = intentBody.intent_id;

      const prodRes = await fetch("/api/catalog/products?limit=1");
      if (!prodRes.ok) throw new Error(`catalog_${prodRes.status}`);
      const prodBody = await prodRes.json();
      const productId = prodBody.items?.[0]?.id;
      if (!productId) throw new Error("no_catalog_product");

      const prepRes = await fetch("/api/phase4/acceptance/prepare", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          intent_id: intentId,
          product_id: productId,
          quantity: 1,
          currency: "INR",
        }),
      });
      if (!prepRes.ok) {
        if (prepRes.status === 409) {
          // A 409 is a REJECTION DECISION, not a trigger failure: render it
          // as a decision card instead of a raw error string.
          let body: unknown = null;
          try {
            body = await prepRes.json();
          } catch {
            body = null;
          }
          const parsed = parseRejection(body);
          if (parsed) {
            setRejection(parsed);
            await fetchRuns();
            return;
          }
          throw new Error("prepare_409");
        }
        const detail = await prepRes.text();
        throw new Error(`prepare_${prepRes.status}:${detail}`);
      }
      await fetchRuns();
    } catch (err) {
      setTriggerError(err instanceof Error ? err.message : "trigger_failed");
    } finally {
      setIsTriggering(false);
    }
  }, [fetchRuns]);

  // Finalize a run: reauthorize + create Razorpay test order.
  const finalizeRun = useCallback(
    async (runId: string) => {
      setFinalizingId(runId);
      try {
        const res = await fetch("/api/phase4/acceptance/finalize", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ run_id: runId }),
        });
        if (!res.ok) {
          const detail = await res.text();
          setTriggerError(`finalize_${res.status}:${detail}`);
        } else {
          await fetchRuns();
        }
      } catch (err) {
        setTriggerError(err instanceof Error ? err.message : "finalize_failed");
      } finally {
        setFinalizingId(null);
      }
    },
    [fetchRuns],
  );

  const matrix = useMemo(
    () => [
      { label: "UCP 2026-04-08", ok: snapshot?.consistency === "MATCH" },
      { label: "AP2 v0.2.0", ok: snapshot?.consistency === "MATCH" },
      { label: "MCP 2026-07-28", ok: snapshot?.consistency === "MATCH" },
      { label: "ACP 2026-01-30", ok: snapshot?.consistency === "MATCH" },
      { label: "A2A v1.0.1", ok: snapshot?.consistency === "MATCH" },
    ],
    [snapshot]
  );

  if (!snapshot) {
    return (
      <section className="container" style={{ padding: "56px 24px 96px" }}>
        <h1 className="page-title">Protocol Gateway</h1>
        <p className="page-sub">Loading…</p>
      </section>
    );
  }

  return (
    <>
      <Section eyebrow="Phase 4" title="Protocol Gateway">
        <p className="prose" style={{ maxWidth: 720 }}>
          The RazorMesh cross-protocol gateway accepts MCP / UCP / AP2 / ACP / A2A inputs,
          verifies the protocol firewall, normalizes to a canonical AgentCommerceIR, runs
          the cross-protocol consistency engine, and routes through Phase-3 trust.
        </p>
        <div className="gateway-decision">
          <Pill tone="allow">FINAL {snapshot.final}</Pill>
          <Pill tone="allow">RAZORGUARD {snapshot.razorGuard}</Pill>
          <Pill tone="allow">FIREWALL {snapshot.firewall}</Pill>
          <Pill tone="allow">CONSISTENCY {snapshot.consistency}</Pill>
        </div>
        <span className="metric__src" data-testid="fixture-sample-note">
          Sample data — fixture snapshot from the Phase-4 proof harness, not a
          live run. Live runs appear in the Live section below.
        </span>
      </Section>

      <Section eyebrow="Envelope" title="Protocol Envelope inspector">
        <div className="card">
          <Field label="Source">{snapshot.envelope.sourceProtocol.toUpperCase()}</Field>
          <Field label="Version">{snapshot.envelope.sourceProtocolVersion}</Field>
          <Field label="Transport">{snapshot.envelope.sourceTransport}</Field>
          <Field label="Message ID">{snapshot.envelope.messageId}</Field>
          <Field label="Request ID">{snapshot.envelope.requestId}</Field>
          <Field label="Idempotency">{snapshot.envelope.idempotencyKey ?? "—"}</Field>
          <Field label="Agent">{snapshot.envelope.agent}</Field>
          <Field label="Merchant">{snapshot.envelope.merchantReference}</Field>
          <Field label="State">{snapshot.envelope.verificationState}</Field>
          <Field label="Payload hash">
            <code>{snapshot.envelope.rawPayloadHash.slice(0, 16)}…</code>
          </Field>
        </div>
      </Section>

      <Section eyebrow="IR" title="AgentCommerceIR inspector">
        <div className="card">
          <Field label="Schema">{snapshot.ir.schemaVersion}</Field>
          <Field label="Merchant">{snapshot.ir.merchant.merchantId}</Field>
          <Field label="Items">{snapshot.ir.items.length}</Field>
          <Field label="Currency">{snapshot.ir.currency}</Field>
          <Field label="Total (minor)">
            {snapshot.ir.totals.totalMinor.toLocaleString("en-IN")}
          </Field>
          <Field label="Recurring">{snapshot.ir.recurring?.mode ?? "none"}</Field>
          <Field label="Intent contract">{snapshot.ir.authorization.intentContractId}</Field>
          <Field label="Authorization generation">
            {snapshot.ir.authorization.authorizationGeneration}
          </Field>
          <Field label="Source protocols">
            {snapshot.ir.provenance.sourceProtocols.join(", ")}
          </Field>
        </div>
      </Section>

      <Section eyebrow="Cross-protocol" title="Consistency matrix">
        <div className="gateway-matrix">
          {matrix.map((m) => (
            <div key={m.label} className="gateway-matrix__row">
              <span className="gateway-matrix__label">{m.label}</span>
              {m.ok ? <Pill tone="allow">MATCH</Pill> : <Pill tone="block">MISMATCH</Pill>}
            </div>
          ))}
        </div>
      </Section>

      <Section eyebrow="Benchmark" title="AgentPay-X results">
        <div className="metrics">
          {snapshot.agentPayX.map((r) => (
            <div key={r.name} className="metric">
              <span className="metric__label">{r.family.replace(/_/g, " ")}</span>
              <p className="metric__value">{r.passed ? "✓" : "✗"}</p>
              <span className="metric__src">{r.name}</span>
            </div>
          ))}
        </div>
        <span className="metric__src">
          Sample data — static proof-harness regression results (AgentPay-X),
          not live traffic.
        </span>
      </Section>

      <Section eyebrow="Live" title="Live acceptance runs (Phase-4 ingress)">
        <div className="seclab-cta" style={{ marginBottom: 16 }}>
          <button
            onClick={triggerLiveRun}
            disabled={isTriggering}
            className="btn btn-primary"
            data-testid="trigger-live-run"
          >
            {isTriggering ? "Triggering…" : "Trigger live acceptance run"}
          </button>
          {triggerError && (
            <p style={{ color: "var(--color-danger)", marginTop: 8 }}>
              Trigger error: <code>{triggerError}</code>
            </p>
          )}
        </div>
        {rejection && (
          <div className="card" style={{ marginTop: 16 }} data-testid="rejection-card">
            <h3 className="card__title">Rejection — {rejection.stage}</h3>
            <Field label="Stage">{rejection.stage}</Field>
            <Field label="Reason">{rejection.reason}</Field>
            <Field label="Protocol firewall">{rejection.firewallStatus}</Field>
            <Field label="Deterministic RazorGuard">{rejection.razorGuardDecision}</Field>
            <Field label="Semantic action">{rejection.semanticAction}</Field>
            <Field label="p(entail) / p(neutral) / p(contra)">
              {rejection.semanticProbabilities
                ? `${fmtProb(rejection.semanticProbabilities[1])} / ${fmtProb(
                    rejection.semanticProbabilities[2],
                  )} / ${fmtProb(rejection.semanticProbabilities[0])}`
                : "—"}
            </Field>
            <Field label="Final decision">{rejection.finalDecision}</Field>
          </div>
        )}
        {liveRuns === null ? (
          <p className="prose" style={{ maxWidth: 720 }}>
            Fetching live acceptance-run registry from <code>/phase4/acceptance/runs</code>…
          </p>
        ) : liveError ? (
          <p className="prose" style={{ maxWidth: 720, color: "var(--color-danger)" }}>
            Live registry unavailable: <code>{liveError}</code>. The static
            AgentPay-X + protocol matrix above remains authoritative for the
            proof-harness regression suite.
          </p>
        ) : liveRuns.length === 0 ? (
          <p className="prose" style={{ maxWidth: 720 }}>
            No live acceptance runs recorded yet. Click the button above to
            trigger one: the system will create a fixture intent, select a catalog
            product, and run the full MCP→UCP→AP2→Firewall→IR→Consistency→RazorGuard
            pipeline. The run will appear here with MCP / UCP / AP2 versions,
            ProtocolEnvelope hash, AgentCommerceIR hash, commerce-commitment-v1,
            consistency verdict, RazorGuard decision, and final ALLOW.
          </p>
        ) : (
          <div className="run-tables">
            {liveRuns.map((run) => {
              const mcp = run.evidence?.mcp;
              const ucp = run.evidence?.ucp;
              const ap2 = run.evidence?.ap2;
              const rm = run.evidence?.razormesh;
              return (
                <table className="run-table" key={run.run_id} data-testid={`run-${run.run_id}`}>
                  <thead>
                    <tr>
                      <th>
                        <div className="run-table__head">
                          <span>Run {run.run_id}</span>
                          <span className="run-table__pills">
                            <Pill tone={run.completed ? "allow" : "challenge"}>
                              {run.completed ? "COMPLETED" : "PREPARED"}
                            </Pill>
                            {rm && (
                              <>
                                <Pill
                                  tone={rm.cross_protocol_consistency === "MATCH" ? "allow" : "block"}
                                >
                                  {rm.cross_protocol_consistency}
                                </Pill>
                                <Pill tone={decisionTone(rm.final_decision)}>{rm.final_decision}</Pill>
                                {!run.completed && (
                                  <button
                                    onClick={() => finalizeRun(run.run_id)}
                                    disabled={finalizingId === run.run_id}
                                    className="btn btn-yellow run-table__finalize"
                                    style={{ fontSize: 12, padding: "6px 12px" }}
                                    data-testid={`finalize-run-${run.run_id}`}
                                  >
                                    {finalizingId === run.run_id ? "Finalizing…" : "Finalize"}
                                  </button>
                                )}
                              </>
                            )}
                          </span>
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <RunRow label="Amount">
                      {run.amount_minor?.toLocaleString("en-IN")} {run.currency}
                    </RunRow>
                    {mcp && (
                      <RunRow label="MCP">
                        <span className="run-sub">
                          {mcp.version} · {mcp.endpoint} · {mcp.method_tool}
                        </span>
                        <br />
                        <code>{mcp.message_id}</code>
                      </RunRow>
                    )}
                    {ucp && (
                      <RunRow label="UCP">
                        <span className="run-sub">
                          {ucp.version} · idem {ucp.idempotency_key}
                        </span>
                        <br />
                        sig/digest: {ucp.signature_digest_verified ? "verified" : "unverified"}
                        {" · "}
                        <code>{ucp.commerce_evidence_hash?.slice(0, 16)}…</code>
                      </RunRow>
                    )}
                    {ap2 && (
                      <RunRow label="AP2">
                        <span className="run-sub">
                          {ap2.version} · {ap2.vct}
                        </span>
                        <br />
                        sig: {ap2.signature_verified ? "verified" : "unverified"} · key binding:{" "}
                        {ap2.key_binding_pop_verified ? "yes" : "no"}
                      </RunRow>
                    )}
                    {rm && (
                      <>
                        <RunRow label="Protocol firewall">
                          {dashIfEmpty(rm.protocol_firewall)}
                          {(rm.protocol_firewall_reasons?.length ?? 0) > 0 && (
                            <>
                              <br />
                              <span className="run-sub">
                                {rm.protocol_firewall_reasons.join(" · ")}
                              </span>
                            </>
                          )}
                        </RunRow>
                        <RunRow label="Deterministic RazorGuard">
                          {dashIfEmpty(rm.razorguard_decision)}
                        </RunRow>
                        <RunRow label="Semantic verifier">
                          {dashIfEmpty(rm.semantic_verifier)}
                          {rm.semantic_verifier && (
                            <>
                              <br />
                              <span className="run-sub">{semanticDetailSubLine(rm)}</span>
                            </>
                          )}
                        </RunRow>
                        <RunRow label="Final decision">
                          <Pill tone={decisionTone(rm.final_decision)}>{rm.final_decision}</Pill>
                        </RunRow>
                        <RunRow label="IR / Envelope / Commit">
                          <code>{rm.agent_commerce_ir_hash?.slice(0, 16)}…</code>
                          {" · "}
                          <code>{rm.protocol_envelope_hash?.slice(0, 16)}…</code>
                          {" · "}
                          <code>{rm.commerce_commitment?.slice(0, 16)}…</code>
                        </RunRow>
                      </>
                    )}
                    <RunRow label="Intent">{run.intent_id}</RunRow>
                    <RunRow label="Checkout">{run.checkout_id}</RunRow>
                  </tbody>
                </table>
              );
            })}
          </div>
        )}
      </Section>

      <Section eyebrow="Audit" title="Audit + receipt">
        <p className="prose" style={{ maxWidth: 720 }}>
          Every protocol gate writes a JCS-canonical hash-chained event to the same Phase-1/2
          audit ledger. The execution attempt, when it occurs, is appended after the
          RazorGuard ALLOW.
        </p>
        <div className="seclab-cta">
          <Link href={snapshot.auditReceiptHref} className="btn btn-primary">
            Open audit dashboard <span aria-hidden="true">→</span>
          </Link>
        </div>
      </Section>
    </>
  );
}
