"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { IntentDraftPanel } from "./IntentDraftPanel";
import { loadRazorpayCheckout } from "@/lib/razorpay";
import styles from "./buyer.module.css";

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
  ticket_json: string | null;
  signature_hex: string | null;
};

type ExecutionState = {
  state: string;
  attempt_id: string;
  detail?: string | { code?: string } | null;
  launch?: {
    public_key_id: string;
    razorpay_order_id: string;
    amount_minor: number;
    currency: string;
    execution_attempt_id: string;
    intent_id: string;
    checkout_id: string;
  } | null;
};

type RazorpayHandlerResponse = {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
};

type StatusBody = {
  state: string;
  attempt_id?: string | null;
  fulfilment_state?: string | null;
  razorpay_payment_status?: string | null;
  error_code?: string | null;
};

type PayPhase = "idle" | "awaiting_checkout" | "verifying" | "captured" | "failed" | "provider_unknown";

type RazorpayInstance = { open: () => void };
declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const fmtINR = (minor: number) =>
  `₹${(minor / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;

const _extractKeywords = (summary: string): string[] => {
  const cleaned = summary.replace(/^requested\s+/i, "");
  const parts = cleaned.split(/[\s/,(]+/).filter((w) => w.length >= 3);
  return parts.length > 0 ? parts : [];
};

const _matchesProductType = (title: string, brand: string | null, keywords: string[]): boolean => {
  const haystack = `${title} ${brand ?? ""}`.toLowerCase();
  return keywords.some((kw) => {
    const lower = kw.toLowerCase();
    return haystack.includes(lower) || haystack.includes(lower.replace(/s$/, ""));
  });
};

export default function BuyerPage() {
  const [intentId, setIntentId] = useState<string | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [selected, setSelected] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [execution, setExecution] = useState<ExecutionState | null>(null);
  const [payPhase, setPayPhase] = useState<PayPhase>("idle");
  const lastLaunchRef = useRef<NonNullable<ExecutionState["launch"]> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [maxBudgetMinor, setMaxBudgetMinor] = useState<number | null>(null);
  const [productSummary, setProductSummary] = useState<string>("");

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const res = await fetch(`${API}/catalog/products?limit=100`);
        if (!res.ok) throw new Error(`catalog ${res.status}`);
        const body = await res.json();
        if (!ignore) {
          setProducts(body.items);
          if (body.items.length > 0) setSelected(body.items[0]);
        }
      } catch (e) {
        if (!ignore) setError(`Catalog unavailable — is the API running? (${String(e)})`);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  // Auto-create the fixture intent on first load so the buyer can
  // immediately click "Propose checkout" without a separate
  // "Create fixture authorization" click. The intent is the
  // minimal synthetic contract for the test path.
  useEffect(() => {
    if (intentId || busy) return;
    let ignore = false;
    (async () => {
      try {
        const res = await fetch(`${API}/buyer/fixture-intent`, { method: "POST" });
        if (!res.ok) return;
        const body = await res.json();
        if (!ignore) setIntentId(body.intent_id);
      } catch {
        // best-effort; the user can still click "Create fixture authorization"
      }
    })();
    return () => {
      ignore = true;
    };
  }, [intentId, busy]);

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
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const propose = async () => {
    if (!intentId || !selected) return;
    setBusy(true);
    setError(null);
    setDecision(null);
    setExecution(null);
    try {
      const res = await fetch(`${API}/buyer/propose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          intent_id: intentId,
          items: [{ product_id: selected.id, quantity }],
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? `propose ${res.status}`);
      setDecision(body);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const execute = async () => {
    if (!intentId || !decision?.ticket_json || !decision.signature_hex) return;
    setBusy(true);
    setError(null);
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
      const body = (await res.json()) as ExecutionState & { detail?: unknown };
      if (!res.ok) {
        const d: unknown = body.detail;
        throw new Error(
          typeof d === "string" ? d : ((d as { code?: string })?.code ?? `execute ${res.status}`),
        );
      }
      setExecution(body);
      if (body.launch) {
        // Server-authoritative launch: browser may not alter any field.
        lastLaunchRef.current = body.launch;
        setPayPhase("awaiting_checkout");
        void openRazorpayCheckout(body.launch);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const submitCallback = useCallback(
    async (payload: RazorpayHandlerResponse, launch: NonNullable<ExecutionState["launch"]>) => {
      setPayPhase("verifying");
      try {
        const res = await fetch(`${API}/buyer/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            execution_attempt_id: launch.execution_attempt_id,
            intent_id: launch.intent_id,
            checkout_id: launch.checkout_id,
            razorpay_payment_id: payload.razorpay_payment_id,
            razorpay_order_id: payload.razorpay_order_id,
            razorpay_signature: payload.razorpay_signature,
          }),
        });
        const body = await res.json();
        if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : (body.detail?.code ?? "callback failed"));
        setExecution((prev) =>
          prev
            ? { ...prev, state: body.state ?? body.decision ?? prev.state }
            : prev,
        );
        const state = String(body.state ?? "");
        if (state === "SUCCEEDED") setPayPhase("captured");
        else if (state === "FAILED") setPayPhase("failed");
        else setPayPhase("provider_unknown");
      } catch (e) {
        setError(`Verification failed: ${String(e)} — the backend remains authoritative.`);
        setPayPhase("provider_unknown");
      }
    },
    [],
  );

  const refreshStatus = useCallback(
    async (launch: NonNullable<ExecutionState["launch"]>) => {
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
        const body = (await res.json()) as StatusBody;
        if (!res.ok) throw new Error(`status ${res.status}`);
        setExecution((prev) => (prev ? { ...prev, state: body.state } : prev));
        if (body.state === "SUCCEEDED") setPayPhase("captured");
        else if (body.state === "FAILED") setPayPhase("failed");
        else if (body.state === "PROVIDER_UNKNOWN") setPayPhase("provider_unknown");
        else if (body.state === "EXECUTING") setPayPhase("awaiting_checkout");
      } catch (e) {
        setError(`Status refresh failed: ${String(e)} — the backend remains authoritative.`);
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const openRazorpayCheckout = async (
    launch: NonNullable<ExecutionState["launch"]>,
  ): Promise<void> => {
    const ok = await loadRazorpayCheckout();
    if (!ok || !window.Razorpay) {
      setError(
        "Razorpay Checkout script failed to load. No payment was initiated; you can retry safely.",
      );
      setPayPhase("idle");
      return;
    }
    const Rz = window.Razorpay;
    if (!Rz) return;
    const rzp = new Rz({
      key: launch.public_key_id,
      order_id: launch.razorpay_order_id,
      amount: launch.amount_minor,
      currency: launch.currency,
      name: "RazorMesh Trust",
      description: "RAZORPAY TEST MODE — simulated payment, no real money",
      theme: { color: "#3399cc" },
      handler: (response: RazorpayHandlerResponse) => {
        void submitCallback(response, launch);
      },
      modal: {
        confirm_close: true,
        ondismiss: () => {
          void refreshStatus(launch);
        },
      },
    });
    rzp.open();
  };

  const stepClass = (done: boolean, active: boolean) =>
    `card ${styles.step} ${done ? styles['step-done'] : ''} ${active ? styles['step-active'] : ''}`;

  const displayProducts = (() => {
    const budgetFiltered = products.filter(
      (p) => maxBudgetMinor === null || p.price_minor <= maxBudgetMinor,
    );
    if (!productSummary) return budgetFiltered;
    const keywords = _extractKeywords(productSummary);
    if (keywords.length === 0) return budgetFiltered;
    const typeFiltered = budgetFiltered.filter((p) => _matchesProductType(p.title, p.brand, keywords));
    return typeFiltered.length > 0 ? typeFiltered : budgetFiltered;
  })();

  return (
    <section aria-labelledby="buyer-title">
      <div className="container">
        <h1 className="page-title" id="buyer-title" style={{ marginBottom: 24 }}>
          Buyer experience
        </h1>
        <IntentDraftPanel
          onDraftConfirmed={(draft) => {
            const hard = draft.payload?.hard as Record<string, unknown> | undefined;
            const maxAmount = hard?.max_amount as { amount_minor?: number } | undefined;
            setMaxBudgetMinor(maxAmount?.amount_minor ?? null);
            setProductSummary(draft.payload?.product_summary ?? "");
          }}
        />
        <p className="page-sub">
          Fixture authorization → catalog → proposed checkout → RazorGuard decision →
          simulated execution. Every decision is produced by the backend — never by this UI.
        </p>

      {error && (
        <div className="card" role="alert" data-testid="buyer-error">
          {error}
        </div>
      )}

      {/* Step 1 */}
      <div className={stepClass(Boolean(intentId), !intentId)} data-testid="step-authorization">
        <h3>Step 1 · Fixture authorization</h3>
        {intentId ? (
          <p data-testid="intent-id">
            Authorized contract <code>{intentId}</code>
          </p>
        ) : (
          <button className="btn btn-secondary btn-sm" onClick={createAuthorization} disabled={busy}>
            Create fixture authorization
          </button>
        )}
      </div>

      {/* Step 2 */}
      <div className={stepClass(Boolean(selected), Boolean(intentId) && !selected)} data-testid="step-catalog">
        <h3>Step 2 · Choose a product</h3>
        {products.length === 0 ? (
          <p>Loading catalog…</p>
        ) : (
          <ul data-testid="product-list">
            {displayProducts.slice(0, 20).map((p) => (
                <li key={p.id}>
                <label>
                  <input
                    type="radio"
                    name="product"
                    checked={selected?.id === p.id}
                    onChange={() => setSelected(p)}
                  />{" "}
                  <strong>{p.title}</strong> — {fmtINR(p.price_minor)}{" "}
                  {p.shipping_minor > 0 && (
                    <span>+ {fmtINR(p.shipping_minor)} shipping</span>
                  )}
                </label>
              </li>
            ))}
          </ul>
        )}
        {selected && (
          <label>
            Quantity{" "}
            <input
              type="number"
              min={1}
              max={2}
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              style={{ width: "4rem" }}
            />
          </label>
        )}
      </div>

      {/* Step 3 */}
      <div className={stepClass(Boolean(decision), Boolean(selected))} data-testid="step-decision">
        <h3>Step 3 · RazorGuard decision</h3>
        {decision ? (
          <>
            <p
              data-testid="decision-banner"
              className={styles[`decision-${decision.decision.toLowerCase()}`]}
            >
              {decision.decision}
              {decision.reason_codes.length > 0 && <> — {decision.reason_codes.join(", ")}</>}
            </p>
            <p>Total (server-recomputed): {fmtINR(decision.total_minor)}</p>
            <p data-testid="authorization-binding" className="page-sub">
              The authorized amount, currency, and checkout contents are bound into the signed
              ticket at decision time. This page cannot change price, order, or payee — any drift
              invalidates the ticket before execution.
            </p>
          </>
        ) : (
          <button className="btn btn-secondary btn-sm" onClick={propose} disabled={!selected || busy}>
            Propose checkout
          </button>
        )}
      </div>

      {/* Step 4 */}
      <div className={stepClass(Boolean(execution), decision?.decision === "ALLOW")} data-testid="step-execution">
        <h3>Step 4 · Trusted execution</h3>
        <p data-testid="test-mode-banner">
          <strong>Razorpay Test Mode — simulated payment, no real money.</strong>
        </p>
        {execution ? (
          <>
            <p data-testid="execution-state" aria-live="polite">
              Payment state: <strong data-testid="pay-state">{payPhase === "captured" ? "CAPTURED/PAID" : payPhase === "verifying" ? "VERIFYING" : payPhase === "failed" ? "FAILED" : payPhase === "provider_unknown" ? "PROVIDER_UNKNOWN" : execution.state}</strong>{" "}
              (attempt <code>{execution.attempt_id}</code>)
            </p>
            {execution.launch && (
              <p data-testid="launch-summary">
                Order <code>{execution.launch.razorpay_order_id}</code> ·{" "}
                {fmtINR(execution.launch.amount_minor)}{" "}
                {execution.launch.currency} — server-issued values only.
              </p>
            )}
            {/* Re-open applies to the SAME server-issued order and only while
                the outcome is genuinely unattempted (M45: PROVIDER_UNKNOWN
                offers no payment action of any kind — refresh only). */}
            {(payPhase === "idle" || payPhase === "awaiting_checkout") && (
              <button
                data-testid="retry-pay"
                disabled={busy}
                onClick={() => {
                  const launch = lastLaunchRef.current;
                  if (launch) void openRazorpayCheckout(launch);
                }}
              >
                Re-open Razorpay Test Checkout
              </button>
            )}
            {(payPhase === "awaiting_checkout" || payPhase === "provider_unknown") && (
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
            {payPhase === "verifying" && (
              <p role="status">Verifying payment server-side… do not close this page.</p>
            )}
            {payPhase === "failed" && (
              <p data-testid="failed-note" role="status">
                Payment failed — nothing was fulfilled. The backend keeps the reservation
                held while it reconciles possible late provider evidence; re-opening or
                starting a fresh payment is intentionally unavailable.
              </p>
            )}
            {payPhase === "provider_unknown" && (
              <p data-testid="unknown-note" role="alert">
                Outcome could not be confirmed yet. The backend holds the reservation and will
                reconcile with the provider — starting a NEW payment is intentionally unavailable.
              </p>
            )}
          </>
        ) : decision?.decision === "ALLOW" ? (
          <button className="btn btn-primary btn-sm" onClick={execute} disabled={busy} data-testid="pay-action">
            Pay securely via Razorpay (Test Mode)
          </button>
        ) : (
          <p>
            {decision
              ? "No ticket issued — execution refused by RazorGuard."
              : "Awaiting an ALLOW decision."}
          </p>
        )}
      </div>

      <div className="card" data-testid="bypass-note">
        <h3>Direct API bypass stays protected</h3>
        <p>
          This UI holds no privileges. Any execution attempt requires a signed,
          context-bound ticket that the backend re-verifies against durable state.
        </p>
      </div>
      </div>
    </section>
  );
}
