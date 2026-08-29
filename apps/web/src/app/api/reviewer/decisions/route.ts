import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { NextResponse } from "next/server";
import { loadCards, packPath } from "../data";

export const DECISION_VALUES = ["contradiction", "entailment", "neutral", "ambiguous_bad_record"] as const;
export type DecisionValue = (typeof DECISION_VALUES)[number];

/**
 * Working decisions store: data/agentpay_ir_v2/review/decisions_working.json
 * Deterministic export shape (sorted by card_id) is produced by /export.
 */
export async function GET() {
  if (process.env.RAZORMESH_REVIEWER_ENABLED !== "1") {
    return NextResponse.json(
      { error: "reviewer disabled; set RAZORMESH_REVIEWER_ENABLED=1" },
      { status: 403 }
    );
  }
  try {
    const p = packPath("decisions_working.json");
    if (!existsSync(p)) return NextResponse.json({ decisions: {}, updated_at: null });
    const body = JSON.parse(readFileSync(p, "utf-8"));
    return NextResponse.json(body);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "load_failed", decisions: {} },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  if (process.env.RAZORMESH_REVIEWER_ENABLED !== "1") {
    return NextResponse.json(
      { error: "reviewer disabled; set RAZORMESH_REVIEWER_ENABLED=1" },
      { status: 403 }
    );
  }
  try {
    const body = (await request.json()) as {
      decisions?: Record<string, { decision: DecisionValue; note?: string }>;
    };
    const decisions = body.decisions ?? {};
    // V3 pack namespace: validate against the frozen card ids themselves, not
    // just the shape (PRE-REVIEW FINAL CORRECTION #3/#5: rc2_* generation).
    const packIds = new Set(loadCards().map((c) => c.card_id));
    for (const [cardId, d] of Object.entries(decisions)) {
      if (!/^rc2_\d{4}$/.test(cardId) || !packIds.has(cardId)) {
        return NextResponse.json({ error: `unknown card_id ${cardId}` }, { status: 422 });
      }
      if (!DECISION_VALUES.includes(d.decision)) {
        return NextResponse.json({ error: `invalid decision for ${cardId}` }, { status: 422 });
      }
    }
    const payload = { updated_at: new Date().toISOString(), decisions };
    writeFileSync(packPath("decisions_working.json"), JSON.stringify(payload, null, 1));
    return NextResponse.json({ saved: true, count: Object.keys(decisions).length });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "save_failed" },
      { status: 500 }
    );
  }
}
