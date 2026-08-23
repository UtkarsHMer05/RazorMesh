export default function BuyerPage() {
  return (
    <section aria-labelledby="buyer-title">
      <h1 className="page-title" id="buyer-title">
        Buyer experience
      </h1>
      <p className="page-sub">
        Fixture authorization → catalog → proposed checkout → RazorGuard decision →
        simulated execution. Full flow lands with Milestone M45; all decisions will be
        produced by the backend, never by this UI.
      </p>
      <div className="card" data-testid="placeholder-note">
        <h3>Under construction (M45)</h3>
        <p>The interactive buyer flow is implemented after the trust core is complete.</p>
      </div>
    </section>
  );
}
