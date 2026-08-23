export default function AuditPage() {
  return (
    <section aria-labelledby="audit-title">
      <h1 className="page-title" id="audit-title">
        Audit dashboard
      </h1>
      <p className="page-sub">
        Chronological evidence timeline with intent/checkout hashes, reason codes,
        ticket/nonce status and audit-chain verification. UI reflects stored evidence only.
      </p>
      <div className="card" data-testid="placeholder-note">
        <h3>Under construction (M25/M47)</h3>
        <p>The evidence ledger API and tamper-verification display land with the ledger milestones.</p>
      </div>
    </section>
  );
}
