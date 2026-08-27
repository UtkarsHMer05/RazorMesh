import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  try {
    const body = await req.text();
    const res = await fetch(`${BACKEND}/phase4/acceptance/prepare`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
      cache: "no-store",
    });
    const respBody = await res.text();
    return new NextResponse(respBody, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "fetch_failed" },
      { status: 502 }
    );
  }
}
