import { NextResponse } from "next/server";
import { loadCards } from "../data";

export async function GET() {
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
