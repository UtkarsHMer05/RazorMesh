import { NextRequest, NextResponse } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const DISPLAY_TRACE_RE = /^RM-[0-9A-HJKMNP-TV-Z]{6}$/;

/**
 * Phase-5 (M011/M013): server-side proxy for the read-only trace API.
 * Strict ID validation before any backend hop; never forwards secrets
 * (the backend projection contains none anyway).
 */
async function proxy(request: NextRequest, traceId: string, suffix = "") {
  if (!DISPLAY_TRACE_RE.test(traceId)) {
    return NextResponse.json({ detail: "Unknown trace" }, { status: 404 });
  }
  const qs = request.nextUrl.search; // forwards only whitelisted-ish params? keep after_seq only
  const params = new URLSearchParams(qs);
  const allowed = new URLSearchParams();
  if (params.get("after_seq")) allowed.set("after_seq", params.get("after_seq") as string);
  const url = `${API}/trace/${traceId}${suffix}${allowed.size ? `?${allowed}` : ""}`;
  try {
    const upstream = await fetch(url, { cache: "no-store" });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Trace API unavailable" }, { status: 502 });
  }
}

export async function GET(
  request: NextRequest,
  ctx: { params: Promise<{ traceId: string }> },
) {
  const { traceId } = await ctx.params;
  return proxy(request, traceId);
}
