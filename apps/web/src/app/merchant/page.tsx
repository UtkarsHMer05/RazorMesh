"use client";

import { useEffect, useMemo, useState } from "react";

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

type Merchant = { id: string; display_name: string };

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const fmtINR = (minor: number) =>
  `₹${(minor / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;

export default function MerchantPage() {
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const [merchantRes, productRes] = await Promise.all([
          fetch(`${API}/catalog/merchants?limit=100`),
          fetch(`${API}/catalog/products?limit=100`),
        ]);
        if (!merchantRes.ok || !productRes.ok) throw new Error("catalog unavailable");
        const [merchantBody, productBody] = await Promise.all([
          merchantRes.json(),
          productRes.json(),
        ]);
        if (!ignore) {
          setMerchants(merchantBody.items);
          setProducts(productBody.items);
        }
      } catch (cause) {
        if (!ignore) {
          setError(`Merchant catalog unavailable — is the API running? (${String(cause)})`);
        }
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const merchantNames = useMemo(
    () => new Map(merchants.map((merchant) => [merchant.id, merchant.display_name])),
    [merchants],
  );

  return (
    <section aria-labelledby="merchant-title">
      <div className="container">
        <h1 className="page-title" id="merchant-title">Merchant surface</h1>
      <p className="page-sub">
        Live synthetic catalog state used by the buyer flow and Security Lab. Merchant
        descriptions remain untrusted data; prices, condition, currency, fees and recurring
        terms are re-read by trusted backend code before authorization and execution.
      </p>
      {error && <div className="card" role="alert">{error}</div>}
      <div className="card" data-testid="merchant-summary">
        <h3>Synthetic catalog</h3>
        <p>{merchants.length} merchants · {products.length} products · no real offers or money</p>
      </div>
      <div className="card" data-testid="merchant-catalog" style={{ marginTop: 16 }}>
        <div className="table-scroll">
          <table>
            <caption className="sr-only">Synthetic merchant products</caption>
            <thead>
              <tr><th>Merchant</th><th>Product</th><th>Category</th><th>Condition</th><th>Terms</th><th>Price</th></tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id}>
                  <td>{merchantNames.get(product.merchant_id) ?? product.merchant_id}</td>
                  <td>{product.title}</td>
                  <td>{product.category}</td>
                  <td>{product.condition}</td>
                  <td>{product.recurring ? "Monthly recurring" : "One-time"}</td>
                  <td>{product.currency === "INR" ? fmtINR(product.price_minor) : `${product.price_minor} ${product.currency}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      </div>
    </section>
  );
}
