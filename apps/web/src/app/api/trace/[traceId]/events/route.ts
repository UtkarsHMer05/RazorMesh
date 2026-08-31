import { NextRequest, NextResponse } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/**
 * Phase-5 (M011/M013): proxy for incremental trace events (live updates).
 * Forwards only the whitelisted after_seq parameter.
 */
export async function GET(
  request: NextRequest,
  ctx: { params: Promise<{ traceId: string }> },
) {
  const { traceId } = await ctx.params;
  if (!/^RM-[0-9A-HJKMNP-TV-Z]{6}$/.test(traceId)) {
    return NextResponse.json({ detail: "Unknown trace" }, { status: 404 });
  }
  const after = request.nextUrl.searchParams.get("after_seq") ?? "0";
  if (!/^\d{1,10}$/.test(after)) {
    return NextResponse.json({ detail: "Bad after_seq" }, { status: 400 });
  }
  try {
    const upstream = await fetch(`${API}/trace/events/${traceId}?after_seq=${after}`, {
      cache: "no-store",
    });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Trace API unavailable" }, { status: 502 });
  }
}
