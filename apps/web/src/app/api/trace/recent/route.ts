import { NextRequest, NextResponse } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/** Phase-5 (M011/M081): recent-trace cards feed (bounded backend query). */
export async function GET(request: NextRequest) {
  const limitRaw = request.nextUrl.searchParams.get("limit") ?? "12";
  const limit = Number.parseInt(limitRaw, 10);
  const safe = Number.isFinite(limit) && limit >= 1 && limit <= 100 ? limit : 12;
  try {
    const upstream = await fetch(`${API}/trace/recent?limit=${safe}`, { cache: "no-store" });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Trace API unavailable" }, { status: 502 });
  }
}
