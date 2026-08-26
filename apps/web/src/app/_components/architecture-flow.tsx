/**
 * Architecture flow (master prompt §8.C).
 * Restrained inline SVG: black/white, thin dividers, monospace labels.
 * Components: Human Intent → Intent Compiler → Human Confirmation → RazorGuard
 *             → Semantic Verifier → Execution Ticket → Razorpay Test Mode
 *             → Audit.
 */
const NODES = [
  'Human Intent',
  'Intent Compiler',
  'Human Confirmation',
  'RazorGuard',
  'Semantic Verifier',
  'Execution Ticket',
  'Razorpay Test Mode',
  'Audit',
] as const;

export function ArchitectureFlow() {
  return (
    <div
      className="archflow"
      role="img"
      aria-label="Architecture flow from human intent to audit, eight stages"
    >
      <ol className="archflow__list">
        {NODES.map((n, i) => (
          <li key={n} className="archflow__node">
            <span className="archflow__index">{String(i + 1).padStart(2, '0')}</span>
            <span className="archflow__label">{n}</span>
          </li>
        ))}
      </ol>
      <p className="archflow__caption">
        Each arrow is a verified transition: nothing in this chain is
        implicit, and every step leaves evidence.
      </p>
    </div>
  );
}
