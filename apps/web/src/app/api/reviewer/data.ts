import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

export type Card = {
  card_id: string;
  stratum: string;
  source_class: string;
  premise: string;
  hypothesis: string;
};

/** Resolve the frozen V2 review-pack directory (repo root `data/agentpay_ir_v2/review`). */
export function reviewDir(): string {
  const candidates = [
    process.env.RAZORMESH_REVIEW_DIR,
    path.resolve(process.cwd(), "../../data/agentpay_ir_v2/review"),
    path.resolve(process.cwd(), "data/agentpay_ir_v2/review"),
  ].filter((c): c is string => Boolean(c));
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  throw new Error("review pack directory not found");
}

export function packPath(name: string): string {
  return path.join(reviewDir(), name);
}

export function loadCards(): Card[] {
  const raw = readFileSync(packPath("REVIEW_PACK_V2.jsonl"), "utf-8");
  return raw
    .split("\n")
    .filter((l) => l.trim().length > 0)
    .map((l) => JSON.parse(l) as Card);
}
