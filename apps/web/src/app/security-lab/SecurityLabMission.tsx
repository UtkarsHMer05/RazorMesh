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

type MissionEvent = {
  seq: number;
  stage: string;
  kind: string;
  title: string;
  status: string;
  detail: string | null;
};

type MissionResult = {
  mission_id: string;
  title: string;
  attack: boolean;
  trace_id: string;
  intent_id: string;
  checkout_id: string;
  mutations_applied: { kind: string; changed_fields: string[] }[];
  pipeline: string;
  final_decision: string;
  ticket_issued: boolean;
  provider_contacted: boolean;
  stages: { stage: string; status: string; detail: string }[];
  events: MissionEvent[];
  movie_note: string;
};

type MissionCard = {
  mission_id: string;
  title: string;
  description: string;
  attack: boolean;
  pipeline: string;
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// The attack movie stage ORDER the movie renders in. Stage STATE is derived
// per-stage from the mission's REAL trace events below - a stage with no
// event is rendered pending, never a fabricated DONE (G017).
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
  const [suiteRan, setSuiteRan] = useState(false);
  const [suiteBusy, setSuiteBusy] = useState(false);

  // G016/G017: dedicated missions + event-driven movie
  const [missionCards, setMissionCards] = useState<MissionCard[]>([]);
  const [mission, setMission] = useState<MissionResult | null>(null);
  const [missionBusy, setMissionBusy] = useState<string | null>(null);

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
        const missionRes = await fetch(`${API}/security-missions`);
        if (!ignore) setMissionCards((await missionRes.json()).missions ?? []);
      } catch (e) {
        if (!ignore) setError(String(e));
      }
    })();
    return () => {
      ignore = true;
    };
  }, []);

  const runMission = useCallback(async (missionId: string) => {
    setMissionBusy(missionId);
    setError(null);
    try {
      const res = await fetch(`${API}/security-missions/${missionId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail?.detail ?? "mission failed");
      setMission(body as MissionResult);
    } catch (e) {
      setError(String(e));
    } finally {
      setMissionBusy(null);
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

  // G017: the attack movie derives EVERY stage from the mission's REAL trace
  // events. A stage with no backend event renders PENDING - never a
  // fabricated DONE. The old hardcoded "Human DONE / Agent DONE / Merchant
  // DONE" narrative constants are gone.
  const movie = useMemo(() => {
    if (!mission) return [];
    const byStage = new Map<string, MissionEvent>();
    for (const e of mission.events) {
      byStage.set(e.stage, e); // last event per stage wins
    }
    return MOVIE_STAGES.map(([stage, label]) => {
      const ev = byStage.get(stage);
      if (!ev) {
        return {
          stage,
          label,
          status: "—",
          detail: "no backend event for this stage",
          pending: true,
        };
      }
      return {
        stage,
        label,
        status: ev.status,
        detail: ev.detail ?? ev.kind,
        pending: false,
      };
    });
  }, [mission]);

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

      {/* Dedicated attack missions (G016): every card runs THAT mission only */}
      <div className={styles.missionGrid} data-testid="attack-mission-cards">
        {missionCards
          .filter((m) => m.attack)
          .map((card) => (
            <div
              key={card.mission_id}
              className={styles.missionCard}
              data-testid={`mission-${card.mission_id}`}
            >
              <h3>{card.title}</h3>
              <p>{card.description}</p>
              <dl>
                <div>
                  <dt>Pipeline</dt>
                  <dd>{card.pipeline === "acceptance" ? "Live orchestrator (D-056)" : "RazorGuard revalidation"}</dd>
                </div>
              </dl>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => void runMission(card.mission_id)}
                disabled={missionBusy !== null}
                data-testid={`run-mission-${card.mission_id}`}
              >
                {missionBusy === card.mission_id ? "Running…" : "Run this mission"}
              </button>
            </div>
          ))}
        <div className={styles.missionCard} data-testid="mission-safe">
          <h3>Safe mission</h3>
          <p>
            A one-time purchase inside the authorization — the control case: the pipeline ALLOWs
            and the demo still never touches the provider.
          </p>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => void runMission("safe")}
            disabled={missionBusy !== null}
            data-testid="run-mission-safe"
          >
            {missionBusy === "safe" ? "Running…" : "Run safe mission"}
          </button>
        </div>
      </div>

      {/* The full suite is a SEPARATE explicit action (G016) */}
      <div className={styles.campaign} data-testid="full-suite-action">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => void runSuite()}
          disabled={suiteBusy}
          data-testid="run-full-suite"
        >
          {suiteBusy ? "Running full suite…" : "RUN FULL RED-TEAM SUITE (22 scenarios)"}
        </button>
      </div>

      {/* Full-pipeline attack movie (G017): rendered ONLY from real trace events */}
      {mission && (
        <div className={styles.movie} data-testid="attack-movie">
          <h3>
            {mission.attack ? "ATTACK" : "CONTROL"} — {mission.title}{" "}
            {mission.trace_id && <code>{mission.trace_id}</code>}
          </h3>
          <ol className={styles.movieStages}>
            {movie.map((m, i) => (
              <li
                key={m.stage}
                className={`${styles.movieRow} ${m.pending ? styles.moviePending : ""}`}
                data-stage={m.stage}
                data-state={m.status}
                data-pending={m.pending ? "true" : undefined}
                style={{ animationDelay: `${i * 140}ms` }}
              >
                <span className={styles.movieIndex}>{i + 1}</span>
                <span className={styles.movieLabel}>{m.label}</span>
                <span className={styles.movieStatus}>{m.pending ? "PENDING" : m.status}</span>
                <span className={styles.movieDetail}>{m.detail}</span>
              </li>
            ))}
          </ol>
          {mission.provider_contacted === false && (
            <p className={styles.providerZero} data-testid="provider-zero">
              PROVIDER NOT CONTACTED — RAZORPAY CALLS = 0 (audit evidence)
            </p>
          )}
          <p className="page-sub" data-testid="movie-note">
            {mission.movie_note} Final: <strong>{mission.final_decision}</strong> · ticket{" "}
            {mission.ticket_issued ? "issued" : "withheld"}.
          </p>
        </div>
      )}

      {/* AgentPay-X campaign (M074–M077) */}
      <div className={styles.campaign} data-testid="agentpay-campaign">
        <h3>AgentPay-X red-team campaign</h3>
        <p className="page-sub">
          The canonical {campaign?.total ?? 191}-scenario adversarial policy benchmark,
          live. Counters are the benchmark&apos;s own — never a fabricated badge.
          (Exactly-once and provider execution are proven by separate acceptance
          tests; this benchmark is a policy engine, not live provider traffic.)
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
