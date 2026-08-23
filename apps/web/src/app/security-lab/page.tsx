export default function SecurityLabPage() {
  return (
    <section aria-labelledby="lab-title">
      <h1 className="page-title" id="lab-title">
        Security Lab — Synthetic Attack Simulation
      </h1>
      <p className="page-sub">
        Defensive demonstration only. Scenarios run against this local system&apos;s real
        authorization path; nothing here attacks Razorpay or any third party. Expected vs
        actual results are shown only after backend execution.
      </p>
      <div className="card" data-testid="placeholder-note">
        <h3>Under construction (M42–M44, M46)</h3>
        <p>Scenario runner and step-by-step evidence views are implemented after the adversarial evaluation core exists.</p>
      </div>
    </section>
  );
}
