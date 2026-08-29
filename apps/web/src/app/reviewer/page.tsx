"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import styles from "./reviewer.module.css";

type Card = { card_id: string; premise: string; hypothesis: string };
type DecisionValue = "contradiction" | "entailment" | "neutral" | "ambiguous_bad_record";
type Decisions = Record<string, { decision: DecisionValue; note?: string }>;

const DECISIONS: { value: DecisionValue; key: string; label: string; cls: string }[] = [
  { value: "contradiction", key: "1", label: "Contradiction (1)", cls: "pill pill--block" },
  { value: "entailment", key: "2", label: "Entailment (2)", cls: "pill pill--allow" },
  { value: "neutral", key: "3", label: "Neutral (3)", cls: "pill pill--challenge" },
  { value: "ambiguous_bad_record", key: "4", label: "Ambiguous / bad record (4)", cls: "pill" },
];

export default function ReviewerPage() {
  const [cards, setCards] = useState<Card[]>([]);
  const [idx, setIdx] = useState(0);
  const [decisions, setDecisions] = useState<Decisions>({});
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const decisionsRef = useRef<Decisions>({});
  useEffect(() => {
    decisionsRef.current = decisions;
  }, [decisions]);

  const persist = useCallback(async (d: Decisions) => {
    setSaveState("saving");
    try {
      const res = await fetch("/api/reviewer/decisions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ decisions: d }),
      });
      if (!res.ok) throw new Error(await res.text());
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  }, []);

  const scheduleSave = useCallback(
    (d: Decisions) => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => void persist(d), 400);
    },
    [persist]
  );

  useEffect(() => {
    (async () => {
      try {
        const [cardsRes, decRes] = await Promise.all([
          fetch("/api/reviewer/cards"),
          fetch("/api/reviewer/decisions"),
        ]);
        const cardsBody = (await cardsRes.json()) as { cards: Card[] };
        const decBody = (await decRes.json()) as { decisions: Decisions };
        if (!cardsBody.cards?.length) throw new Error("no cards loaded");
        setCards(cardsBody.cards);
        setDecisions(decBody.decisions ?? {});
      } catch (e) {
        setLoadError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, []);

  const decide = useCallback(
    (value: DecisionValue) => {
      const card = cards[idx];
      if (!card) return;
      const next = { ...decisionsRef.current };
      if (next[card.card_id]?.decision === value) {
        delete next[card.card_id]; // toggle off
      } else {
        next[card.card_id] = { decision: value };
      }
      setDecisions(next);
      scheduleSave(next);
    },
    [cards, idx, scheduleSave]
  );

  const move = useCallback(
    (delta: number) => {
      setIdx((i) => Math.min(Math.max(i + delta, 0), Math.max(cards.length - 1, 0)));
    },
    [cards.length]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "TEXTAREA") return;
      if (e.key === "ArrowRight" || e.key === "j") move(1);
      else if (e.key === "ArrowLeft" || e.key === "k") move(-1);
      else if (e.key === "1") decide("contradiction");
      else if (e.key === "2") decide("entailment");
      else if (e.key === "3") decide("neutral");
      else if (e.key === "4") decide("ambiguous_bad_record");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide, move]);

  const card = cards[idx];
  const answered = Object.keys(decisions).length;
  const current = card ? decisions[card.card_id]?.decision : undefined;

  if (loadError) {
    return (
      <main className="card" data-testid="reviewer-error">
        <h1 className="card__title">AgentPay-IR v2 reviewer</h1>
        <p role="alert">Failed to load review pack: {loadError}</p>
      </main>
    );
  }
  if (!card) {
    return (
      <main className="card" data-testid="reviewer-loading">
        <h1 className="card__title">AgentPay-IR v2 reviewer</h1>
        <p>Loading frozen review pack…</p>
      </main>
    );
  }

  return (
    <main className={styles.wrap} data-testid="reviewer-root">
      <h1 className="card__title">AgentPay-IR v2 reviewer</h1>
      <p className={styles.progress} data-testid="reviewer-progress">
        Card <strong data-testid="reviewer-position">{idx + 1}</strong> / {cards.length} · answered{" "}
        <strong data-testid="reviewer-answered">{answered}</strong> ·{" "}
        <span data-testid="reviewer-savestate">{saveState}</span>
      </p>

      <section className="card" data-testid="reviewer-card">
        <p className={styles.meta}>
          {card.card_id}
        </p>
        <h2 className={styles.side}>Evidence (premise)</h2>
        <blockquote className={styles.premise} data-testid="reviewer-premise">
          {card.premise}
        </blockquote>
        <h2 className={styles.side}>Authorization constraint (hypothesis)</h2>
        <blockquote className={styles.hypothesis} data-testid="reviewer-hypothesis">
          {card.hypothesis}
        </blockquote>

        <div className={styles.choices} role="group" aria-label="Label choice">
          {DECISIONS.map((d) => (
            <button
              key={d.value}
              className={`${d.cls} ${current === d.value ? styles.selected : ""}`}
              onClick={() => decide(d.value)}
              data-testid={`label-${d.value}`}
            >
              {d.label}
            </button>
          ))}
        </div>

        <div className={styles.nav}>
          <button className="btn btn-secondary btn-sm" onClick={() => move(-1)} data-testid="prev-card">
            ← Previous
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => move(1)} data-testid="next-card">
            Next →
          </button>
          <a className="btn btn-secondary btn-sm" href="/api/reviewer/export" download="review_decisions_export.json" data-testid="export-link">
            Export decisions JSON
          </a>
        </div>
        <p className={styles.hint}>
          Keyboard: 1 contradiction · 2 entailment · 3 neutral · 4 ambiguous/bad · ←/→ navigate. Autosaves
          after every choice. No suggestions are shown by design.
        </p>
      </section>
    </main>
  );
}
