import { describe, expect, it } from "vitest";
import { loadCards, packPath, REVIEWER_PACK_FILE } from "./data";

/**
 * PRE-REVIEW FINAL CORRECTION #3/#4: the reviewer-facing surface (pack file +
 * loader) must expose ONLY card_id, premise and hypothesis. A test that
 * specifically catches label-bearing metadata such as *_contradiction,
 * *_entailment, *_neutral, plus stratum/source-class/label/role leakage.
 */

const LABEL_BEARING_SUFFIXES = ["_contradiction", "_entailment", "_neutral"];
const FORBIDDEN_KEYS = [
  "stratum",
  "source_class",
  "label",
  "expected_label",
  "label_hint",
  "review_role",
  "role",
  "gold",
  "supervised",
  "source_label",
  "metadata",
];

describe("reviewer pack loader (V3)", () => {
  const cards = loadCards();

  it("loads the frozen V3 pack", () => {
    expect(REVIEWER_PACK_FILE).toBe("REVIEW_PACK_V3.jsonl");
    expect(packPath(REVIEWER_PACK_FILE)).toContain("REVIEW_PACK_V3.jsonl");
    expect(cards.length).toBeGreaterThanOrEqual(600);
  });

  it("exposes exactly card_id, premise, hypothesis on every card", () => {
    for (const card of cards) {
      expect(Object.keys(card).sort()).toEqual(["card_id", "hypothesis", "premise"]);
      expect(card.card_id).toMatch(/^rc2_\d{4}$/);
      expect(card.premise.trim()).not.toBe("");
      expect(card.hypothesis.trim()).not.toBe("");
    }
  });

  it("carries no label-bearing metadata keys", () => {
    for (const card of cards) {
      for (const key of Object.keys(card)) {
        for (const forbidden of [...FORBIDDEN_KEYS, ...LABEL_BEARING_SUFFIXES]) {
          expect(key.toLowerCase()).not.toBe(forbidden);
          expect(key.toLowerCase().endsWith(forbidden)).toBe(false);
        }
      }
    }
  });
});
