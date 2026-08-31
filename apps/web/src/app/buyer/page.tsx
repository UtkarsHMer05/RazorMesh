"use client";

/**
 * Phase-5 Buyer redesign (M019–M034): AI Commerce Mission.
 *
 * Flow: Human Mandate → AI Intent Compiler → Confirm Authority →
 * Shopping Agent (search/rank) → Candidates → Checkout Proposal →
 * Trust decision → Payment (unchanged Razorpay lifecycle, M034).
 *
 * Invariants preserved:
 * - Every displayed number/outcome comes from a backend response.
 * - Preset mandate chips preconfigure INPUTS only, never outcomes.
 * - No provider/model branding in the mission flow (developer drawer only).
 * - Animation never marks a stage done before its real event arrives.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { loadRazorpayCheckout } from "@/lib/razorpay";
import { resolveTraceForIntent, setActiveTraceId, useLiveTrace } from "@/lib/live-trace";
import styles from "./buyer.module.css";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Product = {
  id: string;
  title: string;
  brand: string | null;
  price_minor: number;
  shipping_minor: number;
  currency: string;
};

type Decision = {
  decision: "ALLOW" | "CHALLENGE" | "BLOCK";
  reason_codes: string[];
  checkout_id: string;
  total_minor: number;
  ticket_json?: string;
  signature_hex?: string | null;
};

type ExecutionState = {
  state: string;
  attempt_id: string;
  detail: string | null;
  launch?: {
    public_key_id: string;
    razorpay_order_id: string;
    amount_minor: number;
    currency: string;
    execution_attempt_id: string;
    intent_id: string;
    checkout_id: string;
  };
};

/**
 * Phase-5 (M095/M096) payment FSM per master prompt §14. Every state maps to a
 * real backend/provider event; dismissal is NEVER reported as failure, and
 * unknown provider state never fakes success or failure.
 */
type PayPhase =
  | "idle" // no execution yet
  | "revalidating" // fresh server check before (re)opening checkout
  | "awaiting_checkout" // checkout opened, user interacting
  | "verifying" // success callback verifying server-side
  | "captured" // backend confirmed SUCCEEDED
  | "failed" // provider payment.failed event (auto-close + truthful)
  | "user_dismissed" // modal closed without any failure event
  | "provider_unknown" // unknown outcome — pending reconciliation
  | "pending_reconciliation"; // unknown settled to a pending state

type RazorpayInstance = {
  open: () => void;
  close: () => void;
  on?: (event: string, handler: (payload: unknown) => void) => void;
};
declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}

type DraftView = {
  draft_id: string;
  state: string;
  payload: {
    product_summary?: string;
    hard?: Record<string, unknown>;
    semantic_constraints?: { text: string; family_hint?: string | null }[];
    ambiguities?: { question: string; options?: string[] }[];
    unspecified?: { field: string }[];
  };
  compiler_model: string;
  prompt_version: string;
  superseded_by: string | null;
  intent_id: string | null;
  confirmed_generation: number | null;
};

type SearchCandidate = {
  product_id: string;
  title: string;
  brand: string | null;
  category: string;
  condition: string;
  merchant_id: string;
  unit_price_minor: number;
  shipping_minor: number;
  quantity: number;
  total_minor: number;
  currency: string;
  rank: number;
  why: string[];
  recurring: boolean;
};

type SearchReport = {
  inspected: number;
  eligible: number;
  rejected: number;
  candidates: SearchCandidate[];
  rejected_samples: { product_id: string; title: string; reason_code: string; explanation: string }[];
};

const EXAMPLE_MANDATES = [
  "Buy Sony wireless headphones under ₹5,000 all-in, new only, no subscription.",
  "Order a robot vacuum under ₹30,000 total, one-time purchase only.",
  "Get a smart LED bulb under ₹1,500 including shipping, no recurring fees.",
];

const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
function genUlid(): string {
  const now = Date.now();
  let value = BigInt(now) << BigInt(80);
  const randBytes = new Uint8Array(10);
  crypto.getRandomValues(randBytes);
  for (let i = 0; i < 10; i++) value |= BigInt(randBytes[i]) << BigInt((9 - i) * 8);
  let id = "";
  for (let shift = 125; shift >= 0; shift -= 5) {
    id += CROCKFORD[Number((value >> BigInt(shift)) & BigInt(31))];
  }
  return id;
}

function fmtINR(minor: number): string {
  return `₹${(minor / 100).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function stepClass(done: boolean, active: boolean): string {
  return styles.step + (done ? ` ${styles.stepDone}` : "") + (active ? ` ${styles.stepActive}` : "");
}

export default function BuyerPage() {
  // --- mission state -------------------------------------------------------
  const [mandate, setMandate] = useState("");
  const [compileStages, setCompileStages] = useState<string[]>([]); // done stage ids
  const [compileBusy, setCompileBusy] = useState(false);
  const [draft, setDraft] = useState<DraftView | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [searchReport, setSearchReport] = useState<SearchReport | null>(null);
  const [searchBusy, setSearchBusy] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<SearchCandidate | null>(null);
  const [showFullCatalog, setShowFullCatalog] = useState(false);
  const [showRejected, setShowRejected] = useState(false);
  const [missionTrace, setMissionTrace] = useState<string | null>(null);

  // --- legacy fixture/payment state (preserved contracts) -------------------
  const [products, setProducts] = useState<Product[]>([]);
  const [selected, setSelected] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [intentId, setIntentId] = useState<string | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [execution, setExecution] = useState<ExecutionState | null>(null);
  const [payPhase, setPayPhase] = useState<PayPhase>("idle");
  const [failureReason, setFailureReason] = useState<string | null>(null);
  // A SERVER-settled FAILED attempt is dead: no Try Again on that attempt.
  // A live payment.failed event keeps the attempt eligible for a fresh,
  // revalidated retry (master prompt §8).
  const [settledFailed, setSettledFailed] = useState(false);
  const terminalPhaseRef = useRef<string | null>(null);
  const lastLaunchRef = useRef<NonNullable<ExecutionState["launch"]> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { events: traceEvents, summary: traceSummary } = useLiveTrace({
    active: true,
    autoStop: true,
  });

  // Catalog load (real backend data).
  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const res = await fetch(`${API}/catalog/products?limit=100`);
        if (!res.ok) throw new Error(`catalog ${res.status}`);
        const body = (await res.json()) as { items?: Product[] };
        if (!ignore) {
          setProducts(Array.isArray(body.items) ? body.items : []);
          if (body.items?.length && body.items.length > 0) setSelected(body.items[0]);
        }
      } catch (e) {
        if (!ignore) {
          setProducts([]);
          setError(`Catalog unavailable — is the API running? (${String(e)})`);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  // Auto-create the fixture intent on load (synthetic fallback path; the
  // mission flow replaces it once a compiled mandate is confirmed). F015:
  // suppressed once a draft exists — a late fixture-intent could otherwise
  // race the confirm flow and swap the active intent (and its trace) after
  // the human already confirmed a specific mandate.
  useEffect(() => {
    if (intentId || busy || draft) return;
    let ignore = false;
    (async () => {
      try {
        const res = await fetch(`${API}/buyer/fixture-intent`, { method: "POST" });
        if (!res.ok) return;
        const body = await res.json();
        if (!ignore) setIntentId(body.intent_id);
      } catch {
        // best-effort; the manual button remains
      }
    })();
    return () => {
      ignore = true;
    };
  }, [intentId, busy, draft]);

  // Bind the display trace for the active intent.
  useEffect(() => {
    if (!intentId) return;
    let ignore = false;
    resolveTraceForIntent(intentId)
      .then((summary) => {
        if (!ignore && summary) {
          setMissionTrace(summary.trace_id);
          setActiveTraceId(summary.trace_id);
        }
      })
      .catch(() => undefined);
    return () => {
      ignore = true;
    };
  }, [intentId]);

  // --- AI Intent Compiler (real stage lifecycle) ---------------------------
  const compile = useCallback(async () => {
    setCompileBusy(true);
    setError(null);
    setDraft(null);
    setConfirmed(false);
    setSearchReport(null);
    setSelectedCandidate(null);
    setCompileStages([]);
    const done: string[] = [];
    const mark = (s: string) => {
      done.push(s);
      setCompileStages([...done]);
    };
    try {
      mark("reading"); // request dispatched
      const res = await fetch(`${API}/buyer/intent-drafts/compile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          authorization_text: mandate,
          principal_id: `usr_${genUlid()}`,
          agent_id: `agt_${genUlid()}`,
        }),
      });
      mark("extracting"); // response received, parsing constraints
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail?.code ?? `compile failed (${res.status})`);
      }
      const body = (await res.json()) as DraftView;
      mark("validating"); // draft schema validated client-side
      if (!body.draft_id) throw new Error("draft incomplete");
      setDraft(body);
      mark("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCompileBusy(false);
    }
  }, [mandate]);

  // --- Confirmation ceremony (real authority grant) ------------------------
  const decide = useCallback(
    async (action: "confirm" | "reject") => {
      if (!draft) return;
      setConfirmBusy(true);
      setError(null);
      try {
        const res = await fetch(`${API}/buyer/intent-drafts/${draft.draft_id}/${action}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            action === "confirm"
              ? { confirmation_nonce: crypto.randomUUID(), actor: "human" }
              : { actor: "human" },
          ),
        });
        const body = await res.json();
        if (!res.ok) throw new Error(body?.detail?.code ?? `${action} failed`);
        const updated = { ...draft, state: body.state ?? "CONFIRMED", ...body };
        setDraft(updated);
        if (action === "confirm" && body.intent_id) {
          setConfirmed(true);
          setIntentId(body.intent_id);
          setDecision(null);
          setExecution(null);
          setPayPhase("idle");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setConfirmBusy(false);
      }
    },
    [draft],
  );

  // --- Shopping Agent search (real counts, real ranking) -------------------
  const runSearch = useCallback(async () => {
    if (!intentId) return;
    setSearchBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/agent/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intent_id: intentId, quantity, limit: 5 }),
      });
      if (!res.ok) throw new Error(`search failed (${res.status})`);
      const body = (await res.json()) as Partial<SearchReport>;
      const report: SearchReport = {
        inspected: body.inspected ?? 0,
        eligible: body.eligible ?? 0,
        rejected: body.rejected ?? 0,
        candidates: Array.isArray(body.candidates) ? body.candidates : [],
        rejected_samples: Array.isArray(body.rejected_samples) ? body.rejected_samples : [],
      };
      setSearchReport(report);
      setSelectedCandidate(report.candidates[0] ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSearchBusy(false);
    }
  }, [intentId, quantity]);

  // Auto-run search once after a compiled mandate is confirmed.
  const searchedRef = useRef(false);
  useEffect(() => {
    if (confirmed && intentId && !searchedRef.current) {
      searchedRef.current = true;
      void runSearch();
    }
    if (!confirmed) searchedRef.current = false;
  }, [confirmed, intentId, runSearch]);

  // --- Checkout proposal (server is authority) -----------------------------
  const propose = useCallback(async () => {
    const pid = selectedCandidate?.product_id ?? selected?.id;
    if (!intentId || !pid) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/buyer/propose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          intent_id: intentId,
          items: [{ product_id: pid, quantity }],
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(body));
      setDecision(body as Decision);
      if ((body as Decision).decision === "ALLOW") setPayPhase("idle");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [intentId, selectedCandidate, selected, quantity]);

  const submitCallback = useCallback(
    async (r: Record<string, string>, launch: NonNullable<ExecutionState["launch"]>) => {
      // Duplicate callbacks (double fire) are idempotent: the first terminal
      // state wins and later callbacks only re-sync server truth.
      if (terminalPhaseRef.current === "captured" || terminalPhaseRef.current === "failed") {
        return;
      }
      setPayPhase("verifying");
      try {
        const res = await fetch(`${API}/buyer/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            execution_attempt_id: launch.execution_attempt_id,
            intent_id: launch.intent_id,
            checkout_id: launch.checkout_id,
            razorpay_payment_id: r.razorpay_payment_id,
            razorpay_order_id: r.razorpay_order_id,
            razorpay_signature: r.razorpay_signature,
          }),
        });
        const body = await res.json();
        if (!res.ok) throw new Error(body?.detail ?? "callback rejected");
        const next = body.state === "FAILED" ? "failed" : body.state === "SUCCEEDED" ? "captured" : "provider_unknown";
        if (next === "failed" || next === "captured") {
          terminalPhaseRef.current = next;
          setSettledFailed(next === "failed");
        }
        setPayPhase(next);
        setExecution((prev) => (prev ? { ...prev, state: body.state ?? prev.state } : prev));
      } catch {
        setError("Callback could not be verified — the backend remains authoritative.");
        setPayPhase("provider_unknown");
      }
    },
    [],
  );

  const refreshStatus = useCallback(
    async (
      launch: NonNullable<ExecutionState["launch"]>,
      opts?: { dismissed?: boolean },
    ) => {
      // P2-M40: the browser is never a source of payment truth. After the
      // modal is dismissed without a success callback, a webhook may already
      // have settled the attempt — render the SERVER state, not the last
      // local phase.
      setBusy(true);
      setError(null);
      try {
        const res = await fetch(
          `${API}/buyer/status?intent_id=${encodeURIComponent(launch.intent_id)}` +
            `&checkout_id=${encodeURIComponent(launch.checkout_id)}`,
        );
        const body = (await res.json()) as { state?: string };
        if (!res.ok) throw new Error(`status ${res.status}`);
        setExecution((prev) => (prev ? { ...prev, state: body.state ?? prev.state } : prev));
        if (body.state === "SUCCEEDED") {
          terminalPhaseRef.current = "captured";
          setPayPhase("captured");
          setSettledFailed(false);
        } else if (body.state === "FAILED") {
          terminalPhaseRef.current = "failed";
          setPayPhase("failed");
          setSettledFailed(true); // dead attempt — no re-open of the same checkout
        } else if (body.state === "SUCCEEDED" && terminalPhaseRef.current === "failed") {
          // Late capture after a failed event (documented provider behavior):
          // server truth wins and settles the state.
          terminalPhaseRef.current = "captured";
          setPayPhase("captured");
        } else if (body.state === "PROVIDER_UNKNOWN") {
          setPayPhase("provider_unknown");
        } else if (body.state === "EXECUTING") {
          if (opts?.dismissed) {
            // Dismissal without any failure event = USER DISMISSED (never a
            // failure claim). Re-open remains available server-side.
            setPayPhase("user_dismissed");
          } else if (terminalPhaseRef.current === "failed") {
            // §8: a local payment.failed is never erased by a lagging server
            // EXECUTING snapshot — reconciliation settles it; the UI keeps the
            // truthful failure state and the safe Try Again path.
            return;
          } else {
            setPayPhase("awaiting_checkout");
          }
        }
      } catch (e) {
        setError(`Status refresh failed: ${String(e)} — the backend remains authoritative.`);
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  // Phase-5 (M095/M096): the failure/dismiss/success lifecycle is explicit.
  // payment.failed → capture the real failure → close the modal programmatically
  // → truthful PAYMENT FAILED + Try Again. ondismiss without any failure event
  // is USER-DISMISSED, never a failure claim. Unknown stays pending.
  const openRazorpayCheckout = useCallback(
    async (launch: NonNullable<ExecutionState["launch"]>) => {
      const loaded = await loadRazorpayCheckout();
      if (!loaded || !window.Razorpay) {
        setError("Razorpay Checkout could not be loaded in this browser context.");
        setPayPhase("provider_unknown");
        return;
      }
      // A second open on the same attempt re-validates server truth first —
      // never blindly reuse a possibly-consumed/expired authorization.
      setPayPhase("revalidating");
      try {
        const res = await fetch(
          `${API}/buyer/status?intent_id=${encodeURIComponent(launch.intent_id)}` +
            `&checkout_id=${encodeURIComponent(launch.checkout_id)}`,
        );
        if (res.ok) {
          const body = (await res.json()) as { state?: string };
          if (body.state === "SUCCEEDED") {
            setPayPhase("captured");
            setExecution((prev) => (prev ? { ...prev, state: "SUCCEEDED" } : prev));
            return;
          }
          if (body.state === "FAILED") {
            setPayPhase("failed");
            setExecution((prev) => (prev ? { ...prev, state: "FAILED" } : prev));
            return;
          }
        }
      } catch {
        // status probe is advisory; execution continues only with a valid ticket
      }
      setPayPhase("awaiting_checkout");

      let sawFailure = false;
      const rzp = new window.Razorpay({
        key: launch.public_key_id,
        order_id: launch.razorpay_order_id,
        amount: launch.amount_minor,
        currency: launch.currency,
        name: "RazorMesh Trust",
        description: "Test Mode checkout through the trusted executor",
        handler: (r: Record<string, string>) => void submitCallback(r, launch),
        modal: {
          confirm_close: true,
          ondismiss: () => {
            // Dismissal ≠ failure: without a payment.failed event we must not
            // claim failure. Re-sync from the server and label accordingly.
            if (sawFailure) return; // failure path already handled
            void refreshStatus(launch, { dismissed: true });
          },
        },
      });
      // payment.failed: the official failure event (checkout.js). Capture the
      // real failure, close the modal automatically, and leave a truthful
      // terminal state with a safe reason (no raw provider internals).
      type FailureEvent = { error?: { description?: string; code?: string } };
      const onFailure = (payload: unknown): void => {
        const resp = (payload ?? {}) as FailureEvent;
        sawFailure = true;
        terminalPhaseRef.current = "failed";
        const raw = resp.error?.description ?? "";
        const safeReason = raw ? ` (${raw.slice(0, 80)})` : "";
        setPayPhase("failed");
        setFailureReason(`The payment failed${safeReason}. Nothing was fulfilled.`);
        try {
          rzp.close(); // auto-close the modal — the §8 bug fix
        } catch {
          // close() unsupported in some checkout builds; the state is truthful anyway
        }
        // Server truth wins even after a local failure event.
        void refreshStatus(launch, {});
      };
      rzp.on?.("payment.failed", onFailure);
      rzp.open();
    },
    [submitCallback, refreshStatus],
  );

  const execute = useCallback(async () => {
    if (!intentId || !decision?.ticket_json || !decision.signature_hex) return;
    // Race guard: ignore double-clicks while an execution is in flight.
    if (busy || lastLaunchRef.current) {
      const prior = lastLaunchRef.current;
      if (prior) void openRazorpayCheckout(prior);
      return;
    }
    setBusy(true);
    setError(null);
    setSettledFailed(false);
    setFailureReason(null);
    setPayPhase("awaiting_checkout");
    try {
      const res = await fetch(`${API}/buyer/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          intent_id: intentId,
          checkout_id: decision.checkout_id,
          ticket_json: decision.ticket_json,
          signature_hex: decision.signature_hex,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body?.detail ?? "execution rejected");
      setExecution(body as ExecutionState);
      if (body.launch) {
        lastLaunchRef.current = body.launch;
        await openRazorpayCheckout(body.launch);
      }
    } catch (e) {
      setError(String(e));
      setPayPhase("idle");
    } finally {
      setBusy(false);
    }
  }, [intentId, decision, openRazorpayCheckout, busy]);

  const createAuthorization = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/buyer/fixture-intent`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const body = await res.json();
      setIntentId(body.intent_id);
      setDecision(null);
      setExecution(null);
      setPayPhase("idle");
      setMissionTrace(null);
      setDraft(null);
      setConfirmed(false);
      setSearchReport(null);
      setSelectedCandidate(null);
      searchedRef.current = false;
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  // --- derived constraint cards (from the real draft payload) --------------
  const hard = useMemo(
    () =>
      (draft?.payload?.hard ?? {}) as {
        max_amount?: { currency?: string; amount_minor?: number };
        brand_allowlist?: string[];
        condition_allowlist?: string[];
        merchant_allowlist?: string[];
        recurring_forbidden?: boolean;
        quantity_max?: number | null;
      },
    [draft],
  );
  const semanticTexts = useMemo(
    () => draft?.payload?.semantic_constraints?.map((s) => s.text) ?? [],
    [draft],
  );
  const unspecifiedFields = draft?.payload?.unspecified?.map((u) => u.field) ?? [];

  const constraintCards = useMemo(() => {
    const cards: { label: string; value: string; tag: "EXPLICIT" | "INFERRED" | "NOT SPECIFIED" }[] = [];
    const budget = hard.max_amount?.amount_minor;
    if (typeof budget === "number") {
      cards.push({ label: "Budget (all-in)", value: `≤ ${fmtINR(budget)}`, tag: "EXPLICIT" });
    }
    if (hard.brand_allowlist && hard.brand_allowlist.length > 0) {
      cards.push({ label: "Brand", value: hard.brand_allowlist.join(", "), tag: "EXPLICIT" });
    } else if (semanticTexts.some((t) => /brand|sony| preferred/i.test(t))) {
      cards.push({ label: "Brand", value: "Preferred (from your words)", tag: "INFERRED" });
    } else {
      cards.push({ label: "Brand", value: "Any brand", tag: "NOT SPECIFIED" });
    }
    if (hard.condition_allowlist && hard.condition_allowlist.length > 0) {
      cards.push({ label: "Condition", value: hard.condition_allowlist.join(", "), tag: "EXPLICIT" });
    } else if (semanticTexts.some((t) => /new|condition|refurb/i.test(t))) {
      cards.push({ label: "Condition", value: "New (from your words)", tag: "INFERRED" });
    } else {
      cards.push({ label: "Condition", value: "Not specified by you", tag: "NOT SPECIFIED" });
    }
    cards.push({
      label: "Recurring",
      value: hard.recurring_forbidden ? "Forbidden" : "Allowed",
      tag: "EXPLICIT",
    });
    cards.push({
      label: "Merchant",
      value: hard.merchant_allowlist?.length ? hard.merchant_allowlist.join(", ") : "Any merchant",
      tag: hard.merchant_allowlist?.length ? "EXPLICIT" : "NOT SPECIFIED",
    });
    if (draft?.payload?.product_summary) {
      cards.push({ label: "Product", value: draft.payload.product_summary, tag: "EXPLICIT" });
    } else if (semanticTexts.length > 0) {
      cards.push({ label: "Product", value: semanticTexts[0], tag: "INFERRED" });
    }
    if (typeof hard.quantity_max === "number") {
      cards.push({ label: "Max quantity", value: String(hard.quantity_max), tag: "EXPLICIT" });
    }
    return cards;
  }, [draft, hard, semanticTexts]);

  // --- trust mini-pipeline from live trace events (M032) --------------------
  const trustStages = useMemo(() => {
    const stages: { id: string; label: string; status: string }[] = [];
    const razorguard = traceEvents.filter((e) => e.stage === "razorguard").at(-1);
    const semantic = traceEvents.filter((e) => e.stage === "semantic").at(-1);
    const fusion = traceEvents.filter((e) => e.stage === "fusion").at(-1);
    const ticket = traceEvents.filter((e) => e.stage === "ticket").at(-1);
    const provider = traceEvents.filter((e) => e.stage === "provider").at(-1);
    stages.push({ id: "razorguard", label: "RazorGuard rules", status: razorguard?.status ?? "—" });
    stages.push({ id: "semantic", label: "Semantic trust", status: semantic?.status ?? "—" });
    stages.push({ id: "fusion", label: "Fusion", status: fusion?.status ?? "—" });
    stages.push({ id: "ticket", label: "Ticket", status: ticket?.status ?? "—" });
    stages.push({ id: "provider", label: "Provider", status: provider?.status ?? "—" });
    return stages;
  }, [traceEvents]);

  const proposeButtonLabel = decision ? "Re-propose checkout" : "Propose checkout";
  const chosenForProposal = selectedCandidate?.title ?? selected?.title ?? null;

  return (
    <div className="container">
      <h1 className="page-title">Buyer — AI Commerce Mission</h1>
      <p className="page-sub" data-testid="mission-banner">
        <strong>TEST MODE</strong> — no real money. The AI proposes constraints and products;
        authority is granted only by your confirmation, and every decision below is produced by
        the backend — never by this UI.
      </p>

      {error && (
        <div className="card" role="alert" data-testid="buyer-error">
          {error}
        </div>
      )}

      {/* Stage 1: HUMAN MANDATE (M020) */}
      <section className={stepClass(Boolean(mandate), !draft)} data-testid="step-mandate">
        <h2>1 · Human mandate</h2>
        <p className="page-sub">
          Describe what you allow in your own words. The AI only drafts constraints — nothing
          becomes authority until you confirm it.
        </p>
        <label className="field-label" htmlFor="nl-auth">
          Your shopping mandate
        </label>
        <textarea
          id="nl-auth"
          data-testid="nl-input"
          className="text-area"
          value={mandate}
          onChange={(e) => setMandate(e.target.value)}
          rows={3}
          placeholder='e.g. "Buy Sony wireless headphones under ₹5,000 all-in, new only, no subscription."'
        />
        <div className={styles.mandateChips} data-testid="mandate-chips">
          {EXAMPLE_MANDATES.map((m) => (
            <button
              key={m}
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setMandate(m)}
            >
              {m.length > 52 ? `${m.slice(0, 52)}…` : m}
            </button>
          ))}
        </div>
        <button
          data-testid="compile-btn"
          className="btn btn-primary btn-sm"
          onClick={compile}
          disabled={compileBusy || mandate.trim().length < 3}
        >
          {compileBusy ? "Compiling…" : "Compile mandate"}
        </button>
      </section>

      {/* Stage 2: AI INTENT COMPILER (M021–M023) */}
      {(compileStages.length > 0 || draft) && (
        <section className={stepClass(Boolean(draft), compileBusy)} data-testid="step-compiler">
          <h2>2 · AI Intent Compiler</h2>
          <ul className={styles.stageChecklist} data-testid="compile-stages">
            {[
              ["reading", "Reading mandate"],
              ["extracting", "Extracting constraints"],
              ["validating", "Validating"],
              ["ready", "Draft ready"],
            ].map(([id, label]) => (
              <li
                key={id}
                className={compileStages.includes(id) ? styles.stageDone : styles.stagePending}
                aria-current={compileStages.at(-1) === id ? "step" : undefined}
              >
                {compileStages.includes(id) ? "✓" : "•"} {label}
              </li>
            ))}
          </ul>

          {draft && (
            <div data-testid="draft-view">
              <p data-testid="draft-state" aria-live="polite">
                State: <strong>{draft.state}</strong>
                {draft.confirmed_generation !== null && (
                  <> · generation {draft.confirmed_generation}</>
                )}
              </p>

              <div className={styles.constraintGrid} data-testid="constraint-cards">
                {constraintCards.map((c) => (
                  <div key={c.label} className={styles.constraintCard} data-tag={c.tag}>
                    <span className={styles.constraintLabel}>{c.label}</span>
                    <span className={styles.constraintValue}>{c.value}</span>
                    <span
                      className={`${styles.constraintTag} ${
                        c.tag === "EXPLICIT"
                          ? styles.tagExplicit
                          : c.tag === "INFERRED"
                            ? styles.tagInferred
                            : styles.tagUnspecified
                      }`}
                    >
                      {c.tag === "NOT SPECIFIED" ? "Not specified by you" : c.tag}
                    </span>
                  </div>
                ))}
              </div>

              {semanticTexts.length > 0 && (
                <ul data-testid="draft-semantic" className={styles.semanticList}>
                  {semanticTexts.map((t, i) => (
                    <li key={i}>{t}</li>
                  ))}
                </ul>
              )}
              {unspecifiedFields.length > 0 && (
                <p className="page-sub" data-testid="draft-unspecified">
                  Unspecified by you: {unspecifiedFields.join(", ")} — the agent will propose,
                  you decide.
                </p>
              )}
              {(draft.payload.ambiguities?.length ?? 0) > 0 && (
                <div role="note" data-testid="draft-ambiguities">
                  <strong>Clarify:</strong>{" "}
                  {draft.payload.ambiguities!.map((a) => a.question).join(" ")}
                </div>
              )}
              <details className={styles.devDrawer}>
                <summary>Developer view — raw draft</summary>
                <pre data-testid="draft-hard">{JSON.stringify(draft.payload.hard ?? {}, null, 2)}</pre>
                <p className="page-sub">
                  compiled by {draft.compiler_model} · prompt {draft.prompt_version}
                </p>
              </details>
            </div>
          )}
        </section>
      )}

      {/* Stage 3: CONFIRM AUTHORITY (M024) */}
      {draft && draft.state === "DRAFT" && (
        <section className={styles.confirmCeremony} data-testid="step-confirm">
          <h2>3 · Confirm authority</h2>
          <p className="page-sub">
            You are about to grant authority for this mission. The AI holds none until you confirm.
          </p>
          <div className={styles.confirmActions}>
            <button
              data-testid="confirm-draft"
              className="btn btn-primary"
              onClick={() => decide("confirm")}
              disabled={confirmBusy}
            >
              Confirm — grant authority
            </button>
            <button
              data-testid="reject-draft"
              className="btn btn-secondary"
              onClick={() => decide("reject")}
              disabled={confirmBusy}
            >
              Reject draft
            </button>
          </div>
        </section>
      )}
      {confirmed && (
        <section className={`${styles.confirmCeremony} ${styles.authorityGranted}`} data-testid="confirmed-note">
          <h2>
            <span aria-hidden="true">■</span> AUTHORITY GRANTED
          </h2>
          {missionTrace && (
            <p data-testid="mission-trace">
              Live mission <strong className={styles.missionTrace}>{missionTrace}</strong> —
              follows you on every page.
            </p>
          )}
          <p className="page-sub">
            Generation {draft?.confirmed_generation ?? 1}. The confirmed mandate is bound; the
            agent may now search and propose — but only RazorGuard can authorize money.
          </p>
        </section>
      )}
      {draft?.state === "REJECTED" && (
        <p data-testid="rejected-note" className="card">
          Draft rejected. Nothing was authorized.
        </p>
      )}
      {draft?.state === "NEEDS_CLARIFICATION" && (
        <p data-testid="clarify-note" className="card">
          Resolve the ambiguities above by compiling a more specific mandate.
        </p>
      )}

      {/* Stage 4: SHOPPING AGENT (M025–M030) */}
      {(confirmed || searchReport) && (
        <section className={stepClass(Boolean(searchReport), searchBusy)} data-testid="step-agent">
          <h2>4 · Shopping Agent</h2>
          <ul className={styles.stageChecklist} data-testid="agent-activity">
            <li className={styles.stageDone}>✓ Reading confirmed mandate</li>
            <li className={searchReport ? styles.stageDone : styles.stagePending}>
              {searchReport ? "✓" : "•"} Inspecting {searchReport?.inspected ?? "…"} catalog
              products {searchReport ? "(real count)" : ""}
            </li>
            <li className={searchReport ? styles.stageDone : styles.stagePending}>
              {searchReport ? "✓" : "•"} Budget + fees + condition + recurring checks{" "}
              {searchReport ? `(${searchReport.eligible} eligible · ${searchReport.rejected} rejected)` : ""}
            </li>
            <li className={searchReport ? styles.stageDone : styles.stagePending}>
              {searchReport ? "✓" : "•"} Ranking candidates
            </li>
          </ul>
          <button className="btn btn-secondary btn-sm" onClick={runSearch} disabled={searchBusy || !intentId}>
            {searchBusy ? "Searching…" : "Search again"}
          </button>

          {searchReport && (
            <>
              <h3>Top candidates</h3>
              <div className={styles.candidateGrid} data-testid="candidate-cards">
                {searchReport.candidates.map((c) => (
                  <button
                    key={c.product_id}
                    type="button"
                    className={`${styles.candidateCard} ${
                      selectedCandidate?.product_id === c.product_id ? styles.candidateSelected : ""
                    }`}
                    data-testid={`candidate-${c.rank}`}
                    aria-pressed={selectedCandidate?.product_id === c.product_id}
                    onClick={() => setSelectedCandidate(c)}
                  >
                    <span className={styles.candidateRank}>#{c.rank}</span>
                    <strong>{c.title}</strong>
                    <span className="page-sub">
                      {c.brand ?? "Unbranded"} · {c.condition} · qty {c.quantity}
                    </span>
                    <span>
                      {fmtINR(c.unit_price_minor)}
                      {c.shipping_minor > 0 ? ` + ${fmtINR(c.shipping_minor)} shipping` : " · free shipping"}
                    </span>
                    <strong>All-in {fmtINR(c.total_minor)}</strong>
                  </button>
                ))}
              </div>

              {selectedCandidate && (
                <div className="card" data-testid="why-chose">
                  <h4>Why the agent chose this</h4>
                  <ul>
                    {selectedCandidate.why.map((w, i) => (
                      <li key={i}>✓ {w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {searchReport.rejected_samples.length > 0 && (
                <div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setShowRejected((v) => !v)}
                    aria-expanded={showRejected}
                    data-testid="toggle-rejected"
                  >
                    {showRejected ? "Hide" : "Show"} rejected candidates ({searchReport.rejected})
                  </button>
                  {showRejected && (
                    <ul className={styles.rejectedList} data-testid="rejected-candidates">
                      {searchReport.rejected_samples.map((r) => (
                        <li key={r.product_id}>
                          <strong>{r.title}</strong> — <code>{r.reason_code}</code>: {r.explanation}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setShowFullCatalog((v) => !v)}
                  aria-expanded={showFullCatalog}
                  data-testid="toggle-catalog"
                >
                  {showFullCatalog ? "Hide" : "Override: browse full catalog"}
                </button>
                <p className="page-sub">
                  Your override is a proposal only — the backend still decides.
                </p>
              </div>
            </>
          )}
        </section>
      )}

      {/* Full catalog override (M030) — preserved radio contract */}
      {(showFullCatalog || !confirmed) && (
        <section className={stepClass(Boolean(selected), Boolean(intentId) && !selected)} data-testid="step-catalog">
          <h3>{confirmed ? "Catalog override" : "Choose a product"}</h3>
          {products.length === 0 ? (
            <p>Loading catalog…</p>
          ) : (
            <ul data-testid="product-list">
              {products.map((p) => (
                <li key={p.id}>
                  <label>
                    <input
                      type="radio"
                      name="product"
                      value={p.id}
                      checked={selected?.id === p.id}
                      onChange={() => {
                        setSelected(p);
                        setSelectedCandidate(null);
                      }}
                    />{" "}
                    <strong>{p.title}</strong>
                    {p.brand ? ` (${p.brand})` : ""} —{" "}
                    {p.shipping_minor > 0 ? (
                      <>
                        {fmtINR(p.price_minor)} + {fmtINR(p.shipping_minor)} shipping
                      </>
                    ) : (
                      fmtINR(p.price_minor)
                    )}
                  </label>
                </li>
              ))}
            </ul>
          )}
          <label className="field-label" htmlFor="qty">
            Quantity
          </label>
          <input
            id="qty"
            data-testid="quantity-input"
            type="number"
            min={1}
            max={10}
            value={quantity}
            onChange={(e) => setQuantity(Math.max(1, Math.min(10, Number(e.target.value) || 1)))}
            className={styles.qtyInput}
          />
          {confirmed && selected && !selectedCandidate && (
            <p className="page-sub" data-testid="override-note">
              Manual selection: this is a proposal only. RazorGuard will re-check every
              constraint server-side.
            </p>
          )}
        </section>
      )}

      {/* Fixture fallback (synthetic path) */}
      <div className={stepClass(Boolean(intentId), !intentId)} data-testid="step-authorization">
        <h3>Fixture authorization (synthetic fallback)</h3>
        {intentId ? (
          <p data-testid="intent-id">
            Authorized contract <code>{intentId}</code>
            {missionTrace && (
              <>
                {" · "}
                <span data-testid="mission-trace" className={styles.missionTrace}>
                  Mission {missionTrace}
                </span>
              </>
            )}
            {" · "}
            <button
              className="btn btn-secondary btn-sm"
              onClick={createAuthorization}
              disabled={busy}
              data-testid="start-new-mission"
            >
              Start new mission
            </button>
          </p>
        ) : (
          <button className="btn btn-secondary btn-sm" onClick={createAuthorization} disabled={busy}>
            Create fixture authorization
          </button>
        )}
      </div>

      {/* Stage 5: CHECKOUT PROPOSAL + TRUST (M031/M032) */}
      <section className={stepClass(Boolean(decision), Boolean(chosenForProposal))} data-testid="step-decision">
        <h2>5 · Checkout proposal & trust decision</h2>
        <p className="page-sub">
          {chosenForProposal
            ? `Proposing: ${chosenForProposal} × ${quantity}`
            : "Confirm a mandate and the agent will propose a checkout."}
        </p>
        <button className="btn btn-primary btn-sm" onClick={propose} disabled={!intentId || !chosenForProposal || busy} data-testid="propose-checkout">
          {proposeButtonLabel}
        </button>

        {decision && (
          <>
            <div className={styles.proposalSummary} data-testid="checkout-proposal">
              <h3>Checkout proposal</h3>
              <dl>
                <div>
                  <dt>Item</dt>
                  <dd>{chosenForProposal}</dd>
                </div>
                <div>
                  <dt>Quantity</dt>
                  <dd>{quantity}</dd>
                </div>
                <div>
                  <dt>Unit price</dt>
                  <dd>
                    {fmtINR(
                      selectedCandidate?.unit_price_minor ?? selected?.price_minor ?? decision.total_minor,
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Shipping</dt>
                  <dd>
                    {fmtINR(selectedCandidate?.shipping_minor ?? selected?.shipping_minor ?? 0)}
                  </dd>
                </div>
                <div>
                  <dt>Total (server-recomputed)</dt>
                  <dd>
                    <strong>{fmtINR(decision.total_minor)}</strong>
                  </dd>
                </div>
              </dl>
            </div>

            <div className={styles.trustPipeline} data-testid="trust-pipeline">
              {trustStages.map((s) => (
                <span
                  key={s.id}
                  className={`${styles.trustStage} ${
                    s.status === "BLOCK" || s.status === "FAILED"
                      ? styles.trustBad
                      : s.status === "PASS" || s.status === "DONE"
                        ? styles.trustGood
                        : s.status === "—"
                          ? styles.trustAbsent
                          : styles.trustWarn
                  }`}
                  data-stage={s.id}
                  data-state={s.status}
                >
                  {s.label}: <strong>{s.status}</strong>
                </span>
              ))}
            </div>

            <p
              data-testid="decision-outcome"
              className={styles[`decision-${decision.decision.toLowerCase()}`] ?? ""}
            >
              {decision.decision}
              {decision.reason_codes.length > 0 && <> — {decision.reason_codes.join(", ")}</>}
            </p>
            <p data-testid="authorization-binding" className="page-sub">
              The authorized amount, currency, and checkout contents are bound into the signed
              ticket at decision time. This page cannot change price, order, or payee — any drift
              invalidates the ticket before execution.
            </p>
          </>
        )}
      </section>

      {/* Stage 6: PAYMENT (preserved lifecycle, M034) */}
      <section className="card" data-testid="step-payment">
        <h3>Trusted execution</h3>
        <p data-testid="test-mode-banner">
          <strong>Razorpay Test Mode — simulated payment, no real money.</strong>
        </p>
        {execution ? (
          <>
            <p data-testid="execution-state" aria-live="polite">
              Payment state:{" "}
              <strong data-testid="pay-state">
                {payPhase === "captured"
                  ? "CAPTURED/PAID"
                  : payPhase === "verifying"
                    ? "VERIFYING"
                    : payPhase === "failed"
                      ? "PAYMENT_FAILED"
                      : payPhase === "user_dismissed"
                        ? "USER_DISMISSED"
                        : payPhase === "provider_unknown"
                          ? "PROVIDER_UNKNOWN"
                          : payPhase === "pending_reconciliation"
                            ? "PENDING_RECONCILIATION"
                            : payPhase === "revalidating"
                              ? "REVALIDATING"
                              : execution.state}
              </strong>{" "}
              (attempt <code>{execution.attempt_id}</code>)
            </p>
            {execution.launch && (
              <p data-testid="launch-summary">
                Order <code>{execution.launch.razorpay_order_id}</code> ·{" "}
                {fmtINR(execution.launch.amount_minor)} {execution.launch.currency} —
                server-issued values only.
              </p>
            )}
            {/* §14 state machine: each state offers exactly its safe actions.
                - failed: TRY AGAIN performs a fresh server revalidation (the
                  old modal was auto-closed by the payment.failed handler).
                - user_dismissed: not a failure; re-open allowed.
                - provider_unknown / pending: NEVER a fresh payment (never
                  double-charge); reconciliation settles it. */}
            {!settledFailed &&
              (payPhase === "failed" ||
                payPhase === "user_dismissed" ||
                payPhase === "idle" ||
                payPhase === "awaiting_checkout") && (
              <button
                data-testid="retry-pay"
                disabled={busy}
                onClick={() => {
                  const launch = lastLaunchRef.current;
                  if (launch) {
                    setFailureReason(null);
                    void openRazorpayCheckout(launch);
                  }
                }}
              >
                {payPhase === "failed" ? "Try again (fresh revalidation)" : "Re-open Razorpay Test Checkout"}
              </button>
            )}
            {(payPhase === "awaiting_checkout" ||
              payPhase === "user_dismissed" ||
              payPhase === "provider_unknown" ||
              payPhase === "pending_reconciliation") && (
              <button
                data-testid="refresh-status"
                disabled={busy}
                onClick={() => {
                  const launch = lastLaunchRef.current;
                  if (launch) void refreshStatus(launch);
                }}
              >
                Refresh status from server
              </button>
            )}
            {payPhase === "revalidating" && (
              <p role="status" data-testid="revalidating-note">
                Re-validating authorization server-side before touching the provider…
              </p>
            )}
            {payPhase === "verifying" && (
              <p role="status">Verifying payment server-side… do not close this page.</p>
            )}
            {payPhase === "failed" && (
              <p data-testid="failed-note" role="status">
                <strong>PAYMENT FAILED.</strong>{" "}
                {failureReason ?? "Payment failed — nothing was fulfilled."}{" "}
                {settledFailed
                  ? "The backend settled this attempt as failed; re-opening the same checkout is intentionally unavailable."
                  : "The modal was closed automatically. Try again runs a fresh server revalidation — no duplicate charge is possible."}
              </p>
            )}
            {payPhase === "user_dismissed" && (
              <p data-testid="dismissed-note" role="status">
                <strong>Checkout closed by you.</strong> No failure occurred and nothing was
                charged. Re-open is available; the server state stays authoritative.
              </p>
            )}
            {(payPhase === "provider_unknown" || payPhase === "pending_reconciliation") && (
              <p data-testid="unknown-note" role="alert">
                <strong>PAYMENT STATUS PENDING — reconciliation required.</strong> The
                provider outcome is unknown, so no new payment action is offered (never
                double-charge). The backend holds the reservation and reconciles with the
                provider.
              </p>
            )}
          </>
        ) : decision?.decision === "ALLOW" && decision.ticket_json ? (
          <button
            className="btn btn-primary btn-sm"
            onClick={execute}
            disabled={busy || payPhase !== "idle"}
            data-testid="pay-action"
          >
            Pay securely via Razorpay (Test Mode)
          </button>
        ) : (
          <p className="page-sub">Awaiting an ALLOW decision.</p>
        )}
      </section>

      {/* Provider boundary on Buyer (M099): audit-backed contact status */}
      {traceSummary && (
        <section className="card" data-testid="provider-boundary">
          <h3>Payment provider boundary</h3>
          <dl>
            <div>
              <dt>Razorpay contacted</dt>
              <dd data-testid="provider-contacted">
                {traceSummary.provider_contacted ? "YES" : "NO — no authority to execute"}
              </dd>
            </div>
            <div>
              <dt>Provider calls</dt>
              <dd data-testid="provider-call-count">{traceSummary.provider_call_count}</dd>
            </div>
          </dl>
          <p className="page-sub">
            Only the trusted executor may contact the provider, and only with a valid signed
            ticket. Counts come from audit evidence — never from this page.
          </p>
        </section>
      )}

      {/* Mission handoffs (M033) */}
      {missionTrace && (
        <section className="card" data-testid="trace-handoffs">
          <h3>Follow this mission</h3>
          <div className={styles.handoffLinks}>
            {[
              ["/protocols", "Protocols"],
              ["/security-lab", "Security Lab"],
              ["/audit", "Audit"],
              ["/merchant", "Merchant"],
            ].map(([route, label]) => (
              <a key={route} className="btn btn-secondary btn-sm" href={`${route}?trace=${missionTrace}`}>
                {label} →
              </a>
            ))}
          </div>
        </section>
      )}

      <section className="card" data-testid="bypass-note">
        <h3>Direct API bypass stays protected</h3>
        <p className="page-sub">
          This UI holds no privileges. Any execution attempt requires a signed, context-bound
          ticket that the backend re-verifies against durable state.
        </p>
      </section>
    </div>
  );
}
