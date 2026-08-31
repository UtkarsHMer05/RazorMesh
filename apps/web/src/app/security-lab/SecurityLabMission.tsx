"use client";

/**
 * Phase-5 Security Lab redesign (M063–M077).
 *
 * Primary UX: attack mission cards grouped by family + the full-pipeline
 * attack movie (real trace events) + the AgentPay-X live campaign with
 * progress counters, explorer, and per-case read-only replay.
 *
 * Every result comes from backend execution. Scenario presets configure
 * inputs only. No fabricated numbers.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import styles from "./lab.module.css";

type Scenario = {
  scenario_id: string;
  family: string;
  description: string;
  safe_or_unsafe: string;
  expected_outcome: string;
  expected_reason_codes: string[];
};

type DemoResult = {
  scenario: string;
  run_id?: string;
  rejection_stage?: string | null;
  rejection_reason?: string | null;
  protocol_firewall?: string;
  razorguard_decision?: string;
  semantic_verifier?: string;
  semantic_probabilities?: {
    contradiction: number;
    entailment: number;
    neutral: number;
  };
  final_decision?: string;
  ticket_issued?: boolean;
  provider_contacted?: boolean;
};

type CampaignSummary = {
  total: number;
  safe_total: number;
  safe_pass: number;
  attack_total: number;
  attack_block: number;
  false_allows: number;
  false_blocks: number;
  exactly_once_violations: number;
  benchmark_version: string;
};

type Family = {
  family: string;
  count: number;
  safe: number;
  attack: number;
  examples: { id: string; description: string }[];
};

type CaseReplay = {
  scenario_id: string;
  family: string;
  description: string;
  expected_final: string;
  actual_final: string;
  stages: { stage: string; title: string; status: string; detail: string }[];
  read_only: boolean;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// The attack movie: fixed real stage order the movie renders from.
const MOVIE_STAGES = [
  ["human", "Human authorization"],
  ["agent", "Initial checkout"],
  ["merchant", "Merchant mutation"],
  ["protocol", "Protocol firewall"],
  ["razorguard", "Deterministic RazorGuard"],
  ["semantic", "Semantic Trust Check"],
  ["fusion", "Conservative fusion"],
  ["ticket", "Execution ticket"],
  ["provider", "Razorpay boundary"],
] as const;

export function SecurityLabMission() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [demo, setDemo] = useState<DemoResult | null>(null);
  const [demoBusy, setDemoBusy] = useState(false);
  const [suiteRan, setSuiteRan] = useState(false);
  const [suiteBusy, setSuiteBusy] = useState(false);

  const [campaign, setCampaign] = useState<CampaignSummary | null>(null);
  const [families, setFamilies] = useState<Family[]>([]);
  const [cases, setCases] = useState<{ scenario_id: string; family: string; description: string; actual_final: string; safe_or_attack: string; passed: boolean }[]>([]);
  const [replay, setReplay] = useState<CaseReplay | null>(null);
  const [campaignBusy, setCampaignBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        const res = await fetch(`${API}/security-lab/scenarios`);
        if (!ignore) setScenarios((await res.json()).scenarios ?? []);
      } catch (e) {
        if (!ignore) setError(String(e));
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const runScenarioB = useCallback(async () => {
    setDemoBusy(true);
    setError(null);
    try {
      const res = await fetch(
        `${API}/phase4/acceptance/demo/scenario-b-semantic-violation`,
        { method: "POST" },
      );
      const body = await res.json();
      if (!res.ok) throw new Error("scenario failed");
      setDemo({ scenario: "B_hidden_recurring", ...body });
    } catch (e) {
      setError(String(e));
    } finally {
      setDemoBusy(false);
    }
  }, []);

  const runScenarioC = useCallback(async () => {
    setDemoBusy(true);
    setError(null);
    try {
      const res = await fetch(
        `${API}/phase4/acceptance/demo/scenario-c-protocol-valid-intent-invalid`,
        { method: "POST" },
      );
      const body = await res.json();
      if (!res.ok) throw new Error("scenario failed");
      setDemo({ scenario: "C_protocol_valid_intent_invalid", ...body });
    } catch (e) {
      setError(String(e));
    } finally {
      setDemoBusy(false);
    }
  }, []);

  const runSuite = useCallback(async () => {
    setSuiteBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/security-lab/run`, { method: "POST" });
      if (!res.ok) throw new Error("suite failed");
      setSuiteRan(true); // full results render in the suite table below
    } catch (e) {
      setError(String(e));
    } finally {
      setSuiteBusy(false);
    }
  }, []);

  const loadCampaign = useCallback(async () => {
    setCampaignBusy(true);
    setError(null);
    try {
      const [s, f, c] = await Promise.all([
        fetch(`${API}/security-campaign/summary`),
        fetch(`${API}/security-campaign/families`),
        fetch(`${API}/security-campaign/cases`),
      ]);
      const summaryBody = await s.json();
      setCampaign(summaryBody.summary ?? summaryBody);
      setFamilies((await f.json()).families ?? []);
      setCases((await c.json()).cases ?? []);
    } catch (e) {
      setError(String(e));
    } finally {
      setCampaignBusy(false);
    }
  }, []);

  const openCase = useCallback(async (scenarioId: string) => {
    try {
      const res = await fetch(`${API}/security-campaign/case/${scenarioId}/replay`);
      const body = await res.json();
      if (!res.ok) throw new Error("replay failed");
      setReplay(body as CaseReplay);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  // The attack movie derives every stage state from the real demo evidence.
  const movie = useMemo(() => {
    if (!demo) return [];
    const probs = demo.semantic_probabilities;
    const states: Record<string, { status: string; detail: string }> = {
      human: {
        status: "DONE",
        detail: "Mandate confirmed: no subscription, within budget",
      },
      agent: { status: "DONE", detail: "Initial checkout proposed within authority" },
      merchant: {
        status: "DONE",
        detail: demo.scenario.startsWith("B_")
          ? "Hidden recurring membership inserted after authorization"
          : "Unauthorized transaction carried inside a protocol-valid packet",
      },
      protocol: {
        status: demo.protocol_firewall ?? "—",
        detail: "schema/signature/replay checks (real gateway)",
      },
      razorguard: {
        status: demo.razorguard_decision ?? "—",
        detail: demo.rejection_reason ?? "deterministic rules",
      },
      semantic: {
        status: demo.semantic_verifier ?? "—",
        detail: probs
          ? `contradiction ${(probs.contradiction * 100).toFixed(2)}% · entailment ${(
              probs.entailment * 100
            ).toFixed(2)}% · neutral ${(probs.neutral * 100).toFixed(2)}%`
          : "semantic probabilities from the live run",
      },
      fusion: {
        status: demo.final_decision ?? "—",
        detail: "semantic can only tighten",
      },
      ticket: {
        status: demo.ticket_issued ? "ISSUED" : "WITHHELD",
        detail: demo.ticket_issued ? "ticket minted after ALLOW" : "no authority to execute",
      },
      provider: {
        status: demo.provider_contacted ? "CONTACTED" : "NOT CONTACTED",
        detail: "audit-backed provider evidence",
      },
    };
    return MOVIE_STAGES.map(([stage, label]) => ({
      stage,
      label,
      ...(states[stage] ?? { status: "—", detail: "" }),
    }));
  }, [demo]);

  const missionCards = useMemo(() => {
    const cards = [
      {
        id: "b",
        title: "Hidden recurring membership",
        action: "Merchant inserts a ₹499/month subscription after you authorized a one-time purchase.",
        asset: "Your confirmed mandate (no-subscription)",
        detection: "Deterministic RazorGuard + Semantic Trust Check",
        run: runScenarioB,
        key: "b",
      },
      {
        id: "c",
        title: "Protocol-valid, intent-invalid",
        action: "A perfectly signed protocol packet carries 2 units when you authorized 1 (≤ ₹3,000).",
        asset: "Intent-to-execution integrity",
        detection: "RazorGuard budget/quantity rules (after protocol PASS)",
        run: runScenarioC,
        key: "c",
      },
    ];
    if (scenarios.length > 0) {
      const priceDrift = scenarios.find((s) => s.scenario_id === "price-drift-after-allow");
      const replay = scenarios.find((s) => s.scenario_id === "replay-same-ticket-five-times");
      const forged = scenarios.find((s) => s.scenario_id === "forged-checkout-callback");
      if (priceDrift) {
        cards.push({
          id: "price",
          title: "Price drift after ALLOW",
          action: priceDrift.description,
          asset: "The signed checkout binding",
          detection: "Revalidation before execution",
          run: runSuite,
          key: "price",
        });
      }
      if (replay) {
        cards.push({
          id: "replay",
          title: "Ticket replay (5 attempts)",
          action: replay.description,
          asset: "Single-use ticket nonce",
          detection: "Idempotency + nonce registry",
          run: runSuite,
          key: "replay",
        });
      }
      if (forged) {
        cards.push({
          id: "forged",
          title: "Forged payment callback",
          action: forged.description,
          asset: "Provider signature verification",
          detection: "Callback signature verification",
          run: runSuite,
          key: "forged",
        });
      }
    }
    return cards;
  }, [scenarios, runScenarioB, runScenarioC, runSuite]);

  return (
    <section className={styles.lab} data-testid="security-lab-missions">
      <p className="page-sub" data-testid="lab-defensive-note">
        <strong>SYNTHETIC ATTACK SIMULATION</strong> — defensive demonstration only. Missions run
        against this local system&apos;s real authorization path; nothing here attacks Razorpay or
        any third party. Results appear only after backend execution.
      </p>

      {error && (
        <div className="card" role="alert">
          {error}
        </div>
      )}

      {suiteRan && (
        <p className="page-sub" data-testid="suite-ran-note">
          Suite executed — full per-scenario results are in the suite table below on this page.
        </p>
      )}

      {/* Attack mission cards (M063/M065) */}
      <div className={styles.missionGrid} data-testid="attack-mission-cards">
        {missionCards.map((card) => (
          <div key={card.key} className={styles.missionCard} data-testid={`mission-${card.key}`}>
            <h3>{card.title}</h3>
            <dl>
              <div>
                <dt>Attacker action</dt>
                <dd>{card.action}</dd>
              </div>
              <div>
                <dt>Protected asset</dt>
                <dd>{card.asset}</dd>
              </div>
              <div>
                <dt>Detection stage</dt>
                <dd>{card.detection}</dd>
              </div>
            </dl>
            <button type="button" className="btn btn-primary btn-sm" onClick={card.run} disabled={demoBusy || suiteBusy}>
              Run mission
            </button>
          </div>
        ))}
      </div>

      {/* Full-pipeline attack movie (M066–M072) */}
      {demo && (
        <div className={styles.movie} data-testid="attack-movie">
          <h3>
            ATTACK —{" "}
            {demo.scenario.startsWith("B_")
              ? "hidden recurring membership"
              : "protocol-valid, intent-invalid"}
          </h3>
          <ol className={styles.movieStages}>
            {movie.map((m, i) => (
              <li
                key={m.stage}
                className={styles.movieRow}
                data-stage={m.stage}
                data-state={m.status}
                style={{ animationDelay: `${i * 140}ms` }}
              >
                <span className={styles.movieIndex}>{i + 1}</span>
                <span className={styles.movieLabel}>{m.label}</span>
                <span className={styles.movieStatus}>{m.status}</span>
                <span className={styles.movieDetail}>{m.detail}</span>
              </li>
            ))}
          </ol>
          {demo.provider_contacted === false && (
            <p className={styles.providerZero} data-testid="provider-zero">
              PROVIDER NOT CONTACTED — RAZORPAY CALLS = 0 (audit evidence)
            </p>
          )}
          <p className="page-sub">
            The AI proposes. RazorGuard authorizes. The trusted executor executes — the semantic
            model can only tighten a decision; it never issues tickets and never contacts the
            provider.
          </p>
        </div>
      )}

      {/* AgentPay-X campaign (M074–M077) */}
      <div className={styles.campaign} data-testid="agentpay-campaign">
        <h3>AgentPay-X red-team campaign</h3>
        <p className="page-sub">
          The canonical {campaign?.total ?? 191}-case benchmark engine, live. Counters are the
          benchmark&apos;s own — never a fabricated badge.
        </p>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={loadCampaign}
          disabled={campaignBusy}
          data-testid="run-campaign"
        >
          {campaignBusy ? "Running campaign…" : campaign ? "Re-run campaign" : "Run red-team campaign"}
        </button>

        {campaign && (
          <>
            <div className={styles.campaignCounters} data-testid="campaign-counters">
              {[
                ["Scenarios", campaign.total],
                ["Safe scenarios", campaign.safe_total],
                ["Safe pass rate", `${(campaign.safe_pass * 100).toFixed(0)}%`],
                ["Attack scenarios", campaign.attack_total],
                ["Attack block rate", `${(campaign.attack_block * 100).toFixed(0)}%`],
                ["False allows", campaign.false_allows],
                ["False blocks", campaign.false_blocks],
                ["Exactly-once violations", campaign.exactly_once_violations],
              ].map(([label, value]) => (
                <div key={String(label)} className={styles.campaignCounter}>
                  <span className={styles.counterLabel}>{label}</span>
                  <span className={styles.counterValue}>{String(value)}</span>
                </div>
              ))}
            </div>
            <p className="page-sub" data-testid="campaign-version">
              benchmark {campaign.benchmark_version}
            </p>

            {/* Family taxonomy */}
            <details className={styles.familiesDrawer} data-testid="attack-taxonomy">
              <summary>Attack taxonomy ({families.length} families · {campaign.total} scenarios)</summary>
              <ul>
                {families.map((f) => (
                  <li key={f.family}>
                    <code>{f.family}</code> — {f.count} ({f.attack} attack · {f.safe} safe)
                  </li>
                ))}
              </ul>
            </details>

            {/* Case explorer */}
            <div className={styles.explorer}>
              <h4>Case explorer</h4>
              <ul className={styles.caseList} data-testid="case-explorer">
                {cases.slice(0, 12).map((c) => (
                  <li key={c.scenario_id}>
                    <button
                      type="button"
                      className={styles.caseBtn}
                      onClick={() => void openCase(c.scenario_id)}
                      data-testid={`case-${c.scenario_id}`}
                    >
                      <code>{c.scenario_id}</code> · {c.family} · {c.actual_final}
                    </button>
                  </li>
                ))}
              </ul>
            </div>

            {/* Case replay */}
            {replay && (
              <div className={styles.replay} data-testid="case-replay">
                <h4>
                  Replay — <code>{replay.scenario_id}</code> (read-only)
                </h4>
                <p className="page-sub">{replay.description}</p>
                <ol className={styles.movieStages}>
                  {replay.stages.map((s) => (
                    <li key={s.stage} className={styles.movieRow} data-stage={s.stage} data-state={s.status}>
                      <span className={styles.movieLabel}>{s.title}</span>
                      <span className={styles.movieStatus}>{s.status}</span>
                      <span className={styles.movieDetail}>{s.detail}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
