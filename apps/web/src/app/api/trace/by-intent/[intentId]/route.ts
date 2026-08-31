import { NextRequest, NextResponse } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const INTENT_RE = /^intent_[0-9A-HJKMNP-TV-Z]{26}$/;

/**
 * Phase-5 (M011/M013): resolve (lazily mint) the display trace for an intent
 * the backend itself created. The backend 404s unknown intents — no minting
 * for rows that do not exist.
 */
export async function GET(_request: NextRequest, ctx: { params: Promise<{ intentId: string }> }) {
  const { intentId } = await ctx.params;
  if (!INTENT_RE.test(intentId)) {
    return NextResponse.json({ detail: "Unknown intent" }, { status: 404 });
  }
  try {
    const upstream = await fetch(`${API}/trace/by-intent/${intentId}`, { cache: "no-store" });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Trace API unavailable" }, { status: 502 });
  }
}
