"use client";

import { useCallback, useEffect, useState } from "react";

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

type ExecutionState = { state: string; attempt_id: string };

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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadProducts = useCallback(async () => {
    try {
      const res = await fetch(`${API}/catalog/products?limit=100`);
      if (!res.ok) throw new Error(`catalog ${res.status}`);
      setProducts((await res.json()).items);
    } catch (e) {
      setError(`Catalog unavailable — is the API running? (${String(e)})`);
    }
  }, []);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

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
      const body = await res.json();
      if (!res.ok)
        throw new Error(
          typeof body.detail === "string" ? body.detail : (body.detail?.code ?? `execute ${res.status}`),
        );
      setExecution(body);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
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
        <h3>Step 4 · Simulated execution</h3>
        {execution ? (
          <p data-testid="execution-state">
            Payment state: <strong>{execution.state}</strong> (attempt{" "}
            <code>{execution.attempt_id}</code>)
          </p>
        ) : decision?.decision === "ALLOW" ? (
          <button onClick={execute} disabled={busy}>
            Execute payment (mock provider)
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
