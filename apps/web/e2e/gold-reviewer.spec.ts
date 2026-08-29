import { expect, test } from "@playwright/test";

/**
 * PVB013 (2026-08-29): SUPERSEDED — this spec targeted the retired Phase-3 v1
 * gold_review.html artifact (window.ROWS embedded). The v1 gold pack is no
 * longer on review duty and the AgentPay-IR v2 reviewer (apps/web/src/app/reviewer)
 * replaces this flow with fresh coverage in e2e/reviewer-v2.spec.ts.
 * Isolated as obsolete tooling per PVB013; kept for history.
 */
test.beforeEach(() => {
  test.skip(true, "superseded by AgentPay-IR v2 reviewer (PVB013 isolation, 2026-08-29)");
});
import { createHash } from "node:crypto";
import * as nodePath from "node:path";

/**
 * P3-M26 BUGFIX regression: gold reviewer must actually render card content.
 *
 * Original root cause: the v2 patch dropped `const r = ROWS[i];` from
 * render(), so pos/total updated but fam/diff/sug/prem/hyp threw on
 * undefined. This spec opens the REAL artifact via file:// like a human.
 *
 * Browser expectations read the embedded window.ROWS as source of truth;
 * byte-equality between that array and gold_review.csv is enforced by the
 * Python integrity suite (tests/test_gold_pack.py + test_frozen_dataset.py).
 */

const GOLD_DIR =
  process.env.RAZORMESH_GOLD_DIR ??
  nodePath.resolve(process.cwd(), "..", "data", "phase3", "gold");

const FIRST = {
  family: "brand_identity",
  difficulty: "easy",
  suggested_label: "contradiction",
  premisePrefix:
    "Product page states: a non-matching competitor brand usb-c cable, priced at ₹5,000.00.",
  hypothesisPrefix: "The human authorized only JBL brand",
};

declare global {
  // top-level `const ROWS` in the reviewer script lives in the page's global
  // lexical scope; augmenting here lets TS see what runtime provides.
  var ROWS: Row[] | undefined;
}

type Row = {
  record_id: string;
  family: string;
  difficulty: string;
  suggested_label: string;
  premise: string;
  hypothesis: string;
};

async function rows(page: {
  evaluate: <T>(fn: () => T) => Promise<T>;
}): Promise<Row[]> {
  const out = await page.evaluate(() => window.ROWS);
  if (!out) throw new Error("reviewer ROWS missing at runtime");
  return out;
}

async function decisions(
  page: {
    evaluate: <T>(fn: () => T) => Promise<T>;
  },
): Promise<Record<string, { label: string; reason?: string }>> {
  return page.evaluate(() =>
    JSON.parse(
      localStorage.getItem("rm_gold_decisions_v1") ?? "{}",
    ) as Record<string, { label: string; reason?: string }>,
  );
}

test.describe("P3-M26 gold reviewer bugfix", () => {
  let pageErrors: string[] = [];

  test.beforeEach(async ({ page }) => {
    pageErrors = [];
    page.on("pageerror", (err) => pageErrors.push(String(err)));
    await page.goto(`file://${GOLD_DIR}/gold_review.html`);
    await expect(page.getByText("/320")).toBeVisible();
  });

  test("320 rows embedded, zero uncaught exceptions", async ({ page }) => {
    expect((await rows(page)).length).toBe(320);
    expect(pageErrors).toEqual([]);
  });

  test("first card renders non-empty values matching verified original", async ({
    page,
  }) => {
    const all = await rows(page);
    expect(all[0].family).toBe(FIRST.family);
    expect(all[0].difficulty).toBe(FIRST.difficulty);
    expect(all[0].suggested_label).toBe(FIRST.suggested_label);
    expect(all[0].premise.startsWith(FIRST.premisePrefix)).toBe(true);
    expect(all[0].hypothesis.startsWith(FIRST.hypothesisPrefix)).toBe(true);

    await expect(page.locator("#fam")).toHaveText("brand_identity");
    await expect(page.locator("#diff")).toHaveText("easy");
    await expect(page.locator("#sug")).toHaveText("contradiction");
    const prem = await page.locator("#prem").textContent();
    const hyp = await page.locator("#hyp").textContent();
    expect(prem!.length).toBeGreaterThan(40);
    expect(hyp!.length).toBeGreaterThan(10);
    expect(pageErrors).toEqual([]);
  });

  test("keyboard 1/2/3/4 + arrows + localStorage round-trip", async ({ page }) => {
    const all = (await rows(page))[0];

    // 1 -> saves entailment for card 1, advances to card 2
    await page.keyboard.press("1");
    let state = await decisions(page);
    expect(state[all.record_id].label).toBe("entailment");
    expect(Object.keys(state)).toHaveLength(1);

    // refresh restores from localStorage
    await page.reload();
    state = await decisions(page);
    expect(state[all.record_id].label).toBe("entailment");

    // arrow back shows saved decision
    await page.keyboard.press("ArrowLeft");
    await expect(page.locator("#decided-label")).toHaveText("saved: entailment");

    // 4 -> invalid entry committed (default reason), then ADVANCES a card.
    // Step back to inspect: reason box reveals with the stored value.
    await page.keyboard.press("4");
    state = await decisions(page);
    expect(state[all.record_id]).toMatchObject({
      label: "invalid",
      reason: "malformed_or_semantically_nonsensical",
    });
    await page.keyboard.press("ArrowLeft");
    await expect(page.locator("#reason-row")).toBeVisible();
    await expect(page.locator("#reason")).toHaveValue(
      "malformed_or_semantically_nonsensical",
    );

    // labeling that card 2 removes the stale invalid structure entirely
    await page.keyboard.press("2");
    state = await decisions(page);
    expect(state[all.record_id].label).toBe("neutral");
    expect(state[all.record_id].reason).toBeUndefined();

    // custom reason typed into the box is captured verbatim on commit;
    // commit advances a card, so step back onto the card to type,
    // re-commit, then step back once more to read it back.
    await page.keyboard.press("ArrowLeft"); // land back on the neutral card
    await page.keyboard.press("4"); // invalid commit on THIS card
    await page.keyboard.press("ArrowLeft"); // view it: box = stored default
    await page.fill("#reason", "garbled sentence");
    await page.keyboard.press("4"); // re-commit SAME card verbatim
    await page.keyboard.press("ArrowLeft");
    state = await decisions(page);
    expect(state[all.record_id].reason).toBe("garbled sentence");
  });

  test("export writes accurate JSON of decided rows only", async ({ page }) => {
    await page.keyboard.press("1"); // decide exactly one card
    const dlPromise = page.waitForEvent("download");
    await page.keyboard.press("e");
    const dl = await dlPromise;
    expect(dl.suggestedFilename()).toBe("gold_decisions.json");
    const chunks: Buffer[] = [];
    for await (const chunk of await dl.createReadStream()) {
      chunks.push(chunk as Buffer);
    }
    const decisions = JSON.parse(Buffer.concat(chunks).toString());
    const ids = Object.keys(decisions);
    expect(ids).toHaveLength(1);
    expect(decisions[ids[0]].label).toBe("entailment"); // invents nothing
  });

  test("content hashes stable across reload (mutation guard)", async ({ page }) => {
    const firstPass = (await rows(page)).map((r) =>
      createHash("sha256")
        .update(`${r.premise}|${r.hypothesis}|${r.suggested_label}`)
        .digest("hex"),
    );
    await page.reload();
    const secondPass = (await rows(page)).map((r) =>
      createHash("sha256")
        .update(`${r.premise}|${r.hypothesis}|${r.suggested_label}`)
        .digest("hex"),
    );
    expect(firstPass).toEqual(secondPass);
    expect((await rows(page))[0].record_id).toMatch(/^air_[0-9A-Z]{26}$/);
    expect(pageErrors).toEqual([]);
  });
});
