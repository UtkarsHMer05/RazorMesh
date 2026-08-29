import { NextResponse } from "next/server";
import { loadCards } from "../data";

/**
 * Local/dev-only by default (PRE-REVIEW FINAL CORRECTION #21): the reviewer is
 * gated behind RAZORMESH_REVIEWER_ENABLED=1 so a normal deployed application
 * never exposes the review pack.
 */
export async function GET() {
  if (process.env.RAZORMESH_REVIEWER_ENABLED !== "1") {
    return NextResponse.json(
      { error: "reviewer disabled; set RAZORMESH_REVIEWER_ENABLED=1" },
      { status: 403 }
    );
  }
  try {
    const cards = loadCards();
    return NextResponse.json({ cards });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "load_failed", cards: [] },
      { status: 500 }
    );
  }
}
