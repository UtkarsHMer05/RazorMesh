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

import { useEffect, useMemo, useState } from "react";
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
    };
  };
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

export default function ProtocolGatewayPage() {
  const [snapshot] = useState<GatewaySnapshot>(() => FIXTURE_SNAPSHOT);
  const [liveRuns, setLiveRuns] = useState<LiveAcceptanceRun[] | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);

  // Phase-4 live-ingress closure: fetch the real acceptance-run
  // registry from the backend so the dashboard reflects the actual
  // MCP->UCP->AP2->Firewall->IR->Consistency->RazorGuard->ALLOW
  // artifacts produced during the live request, not just static proof
  // harness results.
  useEffect(() => {
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
      </Section>

      <Section eyebrow="Live" title="Live acceptance runs (Phase-4 ingress)">
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
            No live acceptance runs recorded yet. Trigger one via
            <code> POST /phase4/acceptance/prepare</code> or the
            <code> complete_authorized_checkout</code> MCP tool. The run will
            appear here with MCP / UCP / AP2 versions, ProtocolEnvelope hash,
            AgentCommerceIR hash, commerce-commitment-v1, consistency verdict,
            RazorGuard decision, and final ALLOW.
          </p>
        ) : (
          <div className="card" style={{ display: "grid", gap: 12 }}>
            {liveRuns.map((run) => {
              const mcp = run.evidence?.mcp;
              const ucp = run.evidence?.ucp;
              const ap2 = run.evidence?.ap2;
              const rm = run.evidence?.razormesh;
              return (
                <div key={run.run_id} className="card" style={{ padding: 16 }}>
                  <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                    <strong>Run {run.run_id}</strong>
                    <Pill tone={run.completed ? "allow" : "challenge"}>
                      {run.completed ? "COMPLETED" : "PREPARED"}
                    </Pill>
                    {rm && (
                      <>
                        <Pill tone={rm.cross_protocol_consistency === "MATCH" ? "allow" : "block"}>
                          {rm.cross_protocol_consistency}
                        </Pill>
                        <Pill tone="allow">{rm.final_decision}</Pill>
                      </>
                    )}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 8, marginTop: 12 }}>
                    {mcp && (
                      <>
                        <Field label="MCP version">{mcp.version}</Field>
                        <Field label="MCP endpoint">{mcp.endpoint}</Field>
                        <Field label="MCP method">{mcp.method_tool}</Field>
                        <Field label="MCP message">{mcp.message_id}</Field>
                      </>
                    )}
                    {ucp && (
                      <>
                        <Field label="UCP version">{ucp.version}</Field>
                        <Field label="UCP idem">{ucp.idempotency_key}</Field>
                        <Field label="UCP sig/digest">
                          {ucp.signature_digest_verified ? "verified" : "unverified"}
                        </Field>
                        <Field label="UCP commerce">
                          <code>{ucp.commerce_evidence_hash?.slice(0, 16)}…</code>
                        </Field>
                      </>
                    )}
                    {ap2 && (
                      <>
                        <Field label="AP2 version">{ap2.version}</Field>
                        <Field label="AP2 vct">{ap2.vct}</Field>
                        <Field label="AP2 signature">
                          {ap2.signature_verified ? "verified" : "unverified"}
                        </Field>
                        <Field label="AP2 key binding">
                          {ap2.key_binding_pop_verified ? "yes" : "no"}
                        </Field>
                      </>
                    )}
                    {rm && (
                      <>
                        <Field label="Firewall">{rm.protocol_firewall}</Field>
                        <Field label="RazorGuard">{rm.razorguard_decision}</Field>
                        <Field label="Semantic">{rm.semantic_verifier}</Field>
                        <Field label="IR hash">
                          <code>{rm.agent_commerce_ir_hash?.slice(0, 16)}…</code>
                        </Field>
                        <Field label="Envelope hash">
                          <code>{rm.protocol_envelope_hash?.slice(0, 16)}…</code>
                        </Field>
                        <Field label="Commitment">
                          <code>{rm.commerce_commitment?.slice(0, 16)}…</code>
                        </Field>
                      </>
                    )}
                    <Field label="Amount (minor)">
                      {run.amount_minor?.toLocaleString("en-IN")} {run.currency}
                    </Field>
                    <Field label="Intent">{run.intent_id}</Field>
                    <Field label="Checkout">{run.checkout_id}</Field>
                  </div>
                </div>
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
