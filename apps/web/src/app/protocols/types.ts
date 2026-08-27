/**
 * Phase-4 protocol types (UI mirror). The actual source of truth
 * is the Python `razormesh_api.protocol` package; this file keeps
 * the UI strictly typed for the fixture snapshot the page renders.
 */

export type SourceProtocol = "mcp" | "ucp" | "ap2" | "acp" | "a2a" | "internal";

export type FirewallDecision =
  | "PROTOCOL_PASS"
  | "PROTOCOL_CHALLENGE"
  | "PROTOCOL_BLOCK";

export type ConsistencyState = "MATCH" | "MISMATCH" | "INSUFFICIENT_EVIDENCE";

export type VerificationState =
  | "received"
  | "verified"
  | "normalized"
  | "cross_protocol_checked"
  | "rejected";

export type ProtocolEnvelope = {
  schemaVersion: string;
  sourceProtocol: SourceProtocol;
  sourceProtocolVersion: string;
  sourceTransport: string;
  adapterVersion: string;
  messageId: string;
  requestId: string;
  idempotencyKey: string | null;
  rawPayloadHash: string;
  signatureEvidence: Record<string, unknown>;
  identityEvidence: Record<string, unknown>;
  capabilityEvidence: Record<string, unknown>;
  agent: string;
  principalReference: string;
  merchantReference: string;
  commercePayloadReference: string;
  authorizationEvidence: Record<string, unknown>[];
  extensionEvidence: Record<string, unknown>[];
  verificationState: VerificationState;
  verificationReasons: string[];
};

export type AgentCommerceIR = {
  schemaVersion: string;
  principalRef: string;
  agentRef: string;
  merchant: { merchantId: string; sellerId?: string | null };
  checkout: { revision: string };
  items: Array<{
    productId: string;
    quantity: { value: number; unit: string; scale: number };
    unitPrice: { valueMinor: number; currency: string };
    brand?: string;
    condition?: string;
  }>;
  totals: { totalMinor: number; subtotalMinor?: number | null };
  currency: string;
  recurring?: { mode: "none" | "monthly" | "annual" | string } | null;
  authorization: {
    intentContractId: string;
    authorizationGeneration: number;
  };
  provenance: { sourceProtocols: string[] };
};

export type AgentPayXResult = {
  name: string;
  family: string;
  safe: boolean;
  expectedBlock: boolean;
  passed: boolean;
  reason: string;
};
