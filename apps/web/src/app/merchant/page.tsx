export default function MerchantPage() {
  return (
    <section aria-labelledby="merchant-title">
      <h1 className="page-title" id="merchant-title">
        Merchant surface
      </h1>
      <p className="page-sub">
        Synthetic catalog and merchant state used by the buyer flow and the Security Lab.
        Merchant content is untrusted data: it can influence proposals, never authority
        (see SECURITY.md §3).
      </p>
      <div className="card" data-testid="placeholder-note">
        <h3>Under construction (M22/M46)</h3>
        <p>The synthetic catalog seed and merchant mutation tools for the Security Lab land with the catalog milestones.</p>
      </div>
    </section>
  );
}
