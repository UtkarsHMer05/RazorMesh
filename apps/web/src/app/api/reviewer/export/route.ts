import { existsSync, readFileSync } from "node:fs";
import { NextResponse } from "next/server";
import { packPath } from "../data";

/**
 * Deterministic JSON export: rows sorted by card_id, canonical key order,
 * no timestamps — identical inputs produce byte-identical output.
 */
export async function GET() {
  try {
    const p = packPath("decisions_working.json");
    if (!existsSync(p)) {
      return NextResponse.json({ error: "no decisions saved yet" }, { status: 404 });
    }
    const working = JSON.parse(readFileSync(p, "utf-8")) as {
      decisions: Record<string, { decision: string; note?: string }>;
    };
    const rows = Object.entries(working.decisions)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([card_id, d]) => ({
        card_id,
        decision: d.decision,
        ...(d.note ? { note: d.note } : {}),
      }));
    const body = JSON.stringify({ export_version: 1, rows }, null, 1);
    return new NextResponse(body, {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "export_failed" },
      { status: 500 }
    );
  }
}
