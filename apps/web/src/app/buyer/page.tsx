"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { loadRazorpayCheckout } from "@/lib/razorpay";

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

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const res = await fetch(`${API}/catalog/products?limit=100`);
        if (!res.ok) throw new Error(`catalog ${res.status}`);
        const body = await res.json();
        if (!ignore) setProducts(body.items);
      } catch (e) {
        if (!ignore) setError(`Catalog unavailable — is the API running? (${String(e)})`);
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

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
      modal: { confirm_close: true },
    });
    rzp.open();
  };

  const stepClass = (done: boolean, active: boolean) =>
    `card step ${done ? "step-done" : ""} ${active ? "step-active" : ""}`;

  return (
    <section aria-labelledby="buyer-title">
      <h1 className="page-title" id="buyer-title">
        Buyer experience
      </h1>
      <p className="page-sub">
        Fixture authorization → catalog → proposed checkout → RazorGuard decision →
        simulated execution. Every decision is produced by the backend — never by this UI.
      </p>

      {error && (
        <div className="card" role="alert" data-testid="buyer-error" style={{ borderColor: "#b00" }}>
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
          <button onClick={createAuthorization} disabled={busy}>
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
            {products.slice(0, 12).map((p) => (
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
              className={`decision-${decision.decision.toLowerCase()}`}
            >
              {decision.decision}
              {decision.reason_codes.length > 0 && <> — {decision.reason_codes.join(", ")}</>}
            </p>
            <p>Total (server-recomputed): {fmtINR(decision.total_minor)}</p>
          </>
        ) : (
          <button onClick={propose} disabled={!selected || busy}>
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
            <p data-testid="execution-state">
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
            {payPhase !== "captured" && payPhase !== "failed" && (
              <button
                data-testid="retry-pay"
                disabled={busy || payPhase === "verifying"}
                onClick={() => {
                  const launch = lastLaunchRef.current;
                  if (launch) void openRazorpayCheckout(launch);
                }}
              >
                Re-open Razorpay Test Checkout
              </button>
            )}
            {payPhase === "verifying" && (
              <p role="status">Verifying payment server-side… do not close this page.</p>
            )}
            {payPhase === "provider_unknown" && (
              <p data-testid="unknown-note" role="alert">
                Outcome could not be confirmed yet. The backend holds the reservation and will
                reconcile with the provider — starting a NEW payment is intentionally unavailable.
              </p>
            )}
          </>
        ) : decision?.decision === "ALLOW" ? (
          <button onClick={execute} disabled={busy} data-testid="pay-action">
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
    </section>
  );
}
