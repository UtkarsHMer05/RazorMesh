import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function GET(req: Request) {
  try {
    const url = new URL(req.url);
    const res = await fetch(`${BACKEND}/catalog/products${url.search || "?limit=1"}`, {
      cache: "no-store",
    });
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "fetch_failed", items: [] },
      { status: 502 },
    );
  }
}
