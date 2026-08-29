import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

/**
 * Reviewer-facing card: ONLY the three fields a human labeler may see
 * (PRE-REVIEW FINAL CORRECTION #3). Stratum/source-class/label metadata lives
 * exclusively in the gitignored private linkage file.
 */
export type Card = {
  card_id: string;
  premise: string;
  hypothesis: string;
};

export const REVIEWER_PACK_FILE = "REVIEW_PACK_V3.jsonl";

/** Resolve the frozen V3 review-pack directory (repo root `data/agentpay_ir_v2/review`). */
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
  const raw = readFileSync(packPath(REVIEWER_PACK_FILE), "utf-8");
  return raw
    .split("\n")
    .filter((l) => l.trim().length > 0)
    .map((l) => JSON.parse(l) as Card);
}
