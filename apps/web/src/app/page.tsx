const PRINCIPLES: ReadonlyArray<{ title: string; body: string }> = [
  {
    title: "The AI proposes",
    body: "A buyer agent may search, rank and propose checkouts. Proposals are never permissions.",
  },
  {
    title: "RazorGuard authorizes",
    body: "Deterministic policy checks the proposal against the human's confirmed Intent Contract — every time, immediately before execution.",
  },
  {
    title: "The trusted executor executes",
    body: "Only a trusted Payment Executor holding a signed, single-use, context-bound execution ticket can trigger a payment-like side effect.",
  },
];

export default function HomePage() {
  return (
    <section aria-labelledby="overview-title">
      <div className="hero">
        <h1 id="overview-title">Intent-to-Execution Integrity</h1>
        <p className="lede">
          RazorMesh Trust verifies — immediately before any payment-like side effect —
          that the exact transaction still matches the human&apos;s confirmed authorization.
          This is the Phase-1 local prototype: every payment is simulated.
        </p>
      </div>
      <div className="card-grid">
        {PRINCIPLES.map((p) => (
          <article className="card" key={p.title}>
            <h3>{p.title}</h3>
            <p>{p.body}</p>
          </article>
        ))}
      </div>
      <div className="card-grid" style={{ marginTop: 16 }}>
        <article className="card">
          <h3>
            <a href="/buyer">Buyer experience →</a>
          </h3>
          <p>Choose an authorization fixture, browse the catalog, propose a checkout and watch RazorGuard decide.</p>
        </article>
        <article className="card">
          <h3>
            <a href="/security-lab">Security Lab →</a>
          </h3>
          <p>Synthetic Attack Simulation: replay, price drift, context theft and more — executed against the real backend.</p>
        </article>
        <article className="card">
          <h3>
            <a href="/audit">Audit dashboard →</a>
          </h3>
          <p>Hash-chained evidence ledger with tamper verification.</p>
        </article>
      </div>
    </section>
  );
}
