import { NextRequest, NextResponse } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/** Phase-5 (M025/M026): Shopping Agent search proxy (real ranking only). */
export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Bad request body" }, { status: 400 });
  }
  const b = body as { intent_id?: unknown; quantity?: unknown; limit?: unknown };
  if (typeof b.intent_id !== "string" || !/^intent_[0-9A-HJKMNP-TV-Z]{26}$/.test(b.intent_id)) {
    return NextResponse.json({ detail: "Unknown intent" }, { status: 404 });
  }
  const payload: Record<string, unknown> = { intent_id: b.intent_id };
  if (typeof b.quantity === "number" && Number.isInteger(b.quantity)) {
    payload.quantity = Math.max(1, Math.min(10, b.quantity));
  }
  if (typeof b.limit === "number" && Number.isInteger(b.limit)) {
    payload.limit = Math.max(1, Math.min(10, b.limit));
  }
  try {
    const upstream = await fetch(`${API}/agent/search`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Agent search unavailable" }, { status: 502 });
  }
}
