/**
 * Evidence metrics (master prompt §20 — every number traces to a committed
 * artifact). All values come from the live evidence files in /docs and
 * /data, surfaced as a constants map so future updates are obvious.
 *
 * Sources (do not change the values without updating the source documents):
 *   - docs/PHASE3_COMPLETION_REPORT.md (final numbers)
 *   - docs/PHASE3_NLI_FINETUNED_METRICS.json (fine-tuned NLI metrics)
 *   - data/phase3/policy/semantic_thresholds.json (semantic-thresholds-v2)
 *   - data/phase3/gold/gold_frozen.json (gold review outcome)
 */

const EVIDENCE = {
  backendTests: {
    value: 522,
    label: 'Backend tests',
    detail: 'pytest, clean-room (M49)',
    source: 'docs/PHASE3_COMPLETION_REPORT.md',
  },
  frontendTests: {
    value: 14,
    label: 'Frontend unit tests',
    detail: 'vitest',
    source: 'PHASE3_STATUS.md M03',
  },
  playwrightTests: {
    value: 6,
    label: 'Playwright E2E',
    detail: 'redesign-scoped; 4 unrelated file:// tests excluded',
    source: 'e2e/',
  },
  secretsLeaked: {
    value: 0,
    label: 'Secrets leaked',
    detail: 'security-check',
    source: 'make security-check',
  },
  humanContradictionsCaught: {
    value: '31/31',
    label: 'Human contradictions BLOCKED (heldout)',
    detail: 'fine-tuned verifier, 0 unsafe entailments',
    source: 'docs/PHASE3_NLI_FINETUNED_METRICS.json',
  },
  unsafeEntailAll: {
    value: 0,
    label: 'Unsafe entail on 119 human contradictions',
    detail: 'closed the M26 zero-shot gap (was 29)',
    source: 'docs/PHASE3_NLI_FINETUNE_EVAL.md',
  },
  thresholds: {
    value: 'τ=0.30 / 0.40',
    label: 'Semantic thresholds',
    detail: 'semantic-thresholds-v2, GOLD_VALIDATED',
    source: 'data/phase3/policy/semantic_thresholds.json',
  },
  e2eBlockF1: {
    value: 0.989,
    label: 'E2E fusion F1 on test (127)',
    detail: 'block P=0.977 R=1.000',
    source: 'docs/PHASE3_END_TO_END_BENCHMARK.json',
  },
} as const;

type Metric = (typeof EVIDENCE)[keyof typeof EVIDENCE];

function isNumberish(v: string | number): v is number {
  return typeof v === 'number';
}

export function EvidenceMetrics() {
  const items = Object.values(EVIDENCE) as ReadonlyArray<Metric>;
  return (
    <div
      className="metrics-grid"
      role="list"
      aria-label="Verified project metrics"
    >
      {items.map((m, i) => {
        const numeric = isNumberish(m.value);
        return (
          <article
            key={i}
            role="listitem"
            className="metric"
            data-source={m.source}
          >
            <p
              className="metric__value"
              style={numeric ? undefined : { fontSize: '1.4rem' }}
            >
              {m.value}
            </p>
            <p className="metric__label">{m.label}</p>
            <p className="metric__detail">{m.detail}</p>
          </article>
        );
      })}
    </div>
  );
}
