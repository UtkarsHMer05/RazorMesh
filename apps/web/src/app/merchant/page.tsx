"use client";

/**
 * Phase-5 Merchant Sandbox (M036–M045).
 *
 * A bounded workspace where a judge can mutate a REAL demo checkout after
 * authorization and watch RazorMesh detect the drift — without touching the
 * confirmed mandate, provider state, or audit history.
 *
 * Everything displayed comes from backend evidence: presets are inputs only;
 * diffs are computed server-side from durable rows; outcomes never hardcoded.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useLiveTrace } from "@/lib/live-trace";
import styles from "./merchant.module.css";

type Product = {
  id: string;
  merchant_id: string;
  title: string;
  category: string;
  condition: string;
  price_minor: number;
  currency: string;
  recurring: boolean;
};

type Preset = { kind: string; label: string };

type MutationResponse = {
  trace_id: string;
  intent_id: string;
  checkout_id: string;
  kind: string;
  label: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  changed_fields: string[];
  note: string;
};

type DiffRow = { field: string; authorized: unknown; current: unknown };

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const fmtINR = (minor: number) =>
  `₹${(minor / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;

export default function MerchantPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [selected, setSelected] = useState<Product | null>(null);
  const [checkout, setCheckout] = useState<{
    intent_id: string;
    checkout_id: string;
    product: { title: string; price_minor: number; condition: string };
  } | null>(null);
  const [diff, setDiff] = useState<DiffRow[]>([]);
  const [lastMutation, setLastMutation] = useState<MutationResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { events: traceEvents, traceId } = useLiveTrace({ active: true });

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const productRes = await fetch(`${API}/catalog/products?limit=100`);
        const presetRes = await fetch(`${API}/merchant-sandbox/presets`);
        if (!productRes.ok) throw new Error("catalog unavailable");
        const productBody = await productRes.json();
        if (!ignore) {
          setProducts(productBody.items ?? []);
          setSelected(productBody.items?.[0] ?? null);
        }
        if (presetRes.ok) {
          const presetBody = await presetRes.json();
          if (!ignore) setPresets(presetBody.presets ?? []);
        }
      } catch (e) {
        if (!ignore) setError(String(e));
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const refreshDiff = useCallback(async (checkoutId: string) => {
    try {
      const res = await fetch(`${API}/merchant-sandbox/diff/${checkoutId}`);
      if (!res.ok) return;
      const body = await res.json();
      setDiff(body.diff ?? []);
    } catch {
      // diff is best-effort in the UI; backend is authority
    }
  }, []);

  useEffect(() => {
    const id = checkout?.checkout_id;
    if (!id) return;
    const t = window.setTimeout(() => void refreshDiff(id), 0);
    return () => window.clearTimeout(t);
  }, [checkout, refreshDiff, traceEvents.length]);

  const createCheckout = useCallback(async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/merchant-sandbox/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: selected.id, quantity: 1 }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? "checkout failed");
      setCheckout(body);
      setLastMutation(null);
      setDiff([]);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [selected]);

  const mutate = useCallback(
    async (kind: string) => {
      if (!checkout) return;
      setBusy(true);
      setError(null);
      try {
        const res = await fetch(
          kind === "revert"
            ? `${API}/merchant-sandbox/revert`
            : `${API}/merchant-sandbox/mutate`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              intent_id: checkout.intent_id,
              checkout_id: checkout.checkout_id,
              kind,
            }),
          },
        );
        const body = await res.json();
        if (!res.ok) throw new Error(body.detail?.detail ?? body.detail ?? "mutation failed");
        setLastMutation(body as MutationResponse);
        await refreshDiff(checkout.checkout_id);
      } catch (e) {
        setError(String(e));
      } finally {
        setBusy(false);
      }
    },
    [checkout, refreshDiff],
  );

  const fmtValue = useCallback((field: string, value: unknown): string => {
    if (value === null || value === undefined) return "—";
    if (field.includes("minor")) return fmtINR(Number(value));
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }, []);

  const mutationEvents = useMemo(
    () =>
      traceEvents.filter(
        (e) => e.stage === "merchant" && (e.kind === "offer.mutated" || e.kind === "offer.reverted"),
      ),
    [traceEvents],
  );

  return (
    <div className="container">
      <h1 className="page-title">Merchant — Offer Sandbox</h1>
      <p className="page-sub" data-testid="merchant-banner">
        <strong>SYNTHETIC / LOCAL DEMO.</strong> Select a real catalog product, authorize a demo
        checkout, then mutate the offer the way an adversarial merchant would — and watch the same
        mission trace show the drift. The confirmed human mandate is never modified; every mutation
        and revert is preserved in the audit ledger.
        {traceId && (
          <>
            {" "}
            Current mission: <strong>{traceId}</strong>
          </>
        )}
      </p>

      {error && (
        <div className="card" role="alert" data-testid="merchant-error">
          {error}
        </div>
      )}

      {/* Product workspace */}
      <section className={styles.workspace} data-testid="merchant-workspace">
        <div className={styles.productPane}>
          <h2>1 · Select a product</h2>
          <ul className={styles.productList} data-testid="sandbox-product-list">
            {products.slice(0, 24).map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  className={`${styles.productRow} ${selected?.id === p.id ? styles.productSelected : ""}`}
                  aria-pressed={selected?.id === p.id}
                  onClick={() => setSelected(p)}
                  data-testid={`product-${p.id}`}
                >
                  <strong>{p.title}</strong>
                  <span>
                    {fmtINR(p.price_minor)} · {p.condition}
                    {p.recurring ? " · recurring" : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <button
            className="btn btn-primary btn-sm"
            onClick={createCheckout}
            disabled={!selected || busy}
            data-testid="create-sandbox-checkout"
          >
            {checkout ? "Start a fresh sandbox checkout" : "Create sandbox checkout"}
          </button>
        </div>

        <div className={styles.offerPane}>
          <h2>2 · Current offer</h2>
          {checkout ? (
            <div className={styles.offerCard} data-testid="current-offer">
              <p>
                <strong>{checkout.product.title}</strong>
              </p>
              <dl>
                <div>
                  <dt>Price</dt>
                  <dd data-testid="offer-price">{fmtINR(checkout.product.price_minor)}</dd>
                </div>
                <div>
                  <dt>Condition</dt>
                  <dd>{checkout.product.condition}</dd>
                </div>
                <div>
                  <dt>Recurring</dt>
                  <dd>
                    {diff.some((d) => d.field === "subscription_terms") ? "Yes (mutated)" : "No"}
                  </dd>
                </div>
                <div>
                  <dt>Checkout</dt>
                  <dd>
                    <code>{checkout.checkout_id}</code>
                  </dd>
                </div>
              </dl>
            </div>
          ) : (
            <p className="page-sub">Create a sandbox checkout to unlock the attack presets.</p>
          )}
        </div>
      </section>

      {/* Attack presets */}
      {checkout && (
        <section className={styles.presetSection} data-testid="attack-presets">
          <h2>3 · Attack presets — mutate the offer</h2>
          <p className="page-sub">
            These preconfigure <em>inputs</em> only. What happens next is decided by the real
            pipeline — never by this page.
          </p>
          <div className={styles.presetGrid}>
            {presets.map((p) => (
              <button
                key={p.kind}
                type="button"
                className={styles.presetBtn}
                onClick={() => mutate(p.kind)}
                disabled={busy}
                data-testid={`preset-${p.kind}`}
              >
                {p.label}
              </button>
            ))}
            <button
              type="button"
              className={`${styles.presetBtn} ${styles.revertBtn}`}
              onClick={() => mutate("revert")}
              disabled={busy}
              data-testid="preset-revert"
            >
              Revert to original offer
            </button>
          </div>
        </section>
      )}

      {/* Before / after diff */}
      {(diff.length > 0 || lastMutation) && (
        <section className={styles.diffSection} data-testid="offer-diff">
          <h2>4 · Authorized vs current</h2>
          <p className="page-sub">
            Only fields that actually changed are highlighted — computed from durable backend rows.
          </p>
          {diff.length > 0 ? (
            <table className={styles.diffTable}>
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Authorized</th>
                  <th>Current</th>
                </tr>
              </thead>
              <tbody>
                {diff.map((d) => (
                  <tr key={d.field} className={styles.diffChanged} data-testid="diff-row">
                    <td>{d.field}</td>
                    <td>{fmtValue(d.field, d.authorized)}</td>
                    <td>
                      <strong>{fmtValue(d.field, d.current)}</strong> ← CHANGED
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p data-testid="no-drift">No drift — the offer matches the authorized state.</p>
          )}
          {lastMutation && (
            <p className="page-sub" data-testid="mutation-note">
              {lastMutation.label}: {lastMutation.note} Changed:{" "}
              {lastMutation.changed_fields.join(", ") || "nothing"}. Trace:{" "}
              <strong>{lastMutation.trace_id || "—"}</strong>
            </p>
          )}
        </section>
      )}

      {/* Trace evidence */}
      {mutationEvents.length > 0 && (
        <section className="card" data-testid="merchant-trace-evidence">
          <h2>Mutation evidence on this mission</h2>
          <ul>
            {mutationEvents.slice(-6).map((e) => (
              <li key={e.seq}>
                <code>#{e.seq}</code> {e.title} — {e.kind} (
                {Array.isArray(e.evidence.changed_fields)
                  ? (e.evidence.changed_fields as string[]).join(", ")
                  : ""}
                )
              </li>
            ))}
          </ul>
          <p className="page-sub">
            Open Audit with the same trace to see the hash-chained record — the mutation history
            can never be erased, even after revert.
          </p>
        </section>
      )}

      <section className="card">
        <h3>Sandbox boundary</h3>
        <p className="page-sub">
          Mutations modify the durable <strong>checkout row</strong> (the post-authorization drift
          surface RazorGuard defends) — never the confirmed IntentContract, never provider state.
          Any execution attempt against a mutated checkout is revalidated server-side and rejected.
        </p>
      </section>
    </div>
  );
}
