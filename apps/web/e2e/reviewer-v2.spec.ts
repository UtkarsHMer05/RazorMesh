import { expect, test } from "@playwright/test";

/**
 * AgentPay-IR v2 reviewer acceptance (PVB correction #5).
 * Coverage runs against the REAL frozen V2 artifact served by /api/reviewer/cards.
 * Assertions: keyboard labels, prev/next, progress, autosave round-trip,
 * deterministic export, and NO suggestion/label-hint leakage in the UI.
 */

const DECISIONS = ["contradiction", "entailment", "neutral", "ambiguous_bad_record"] as const;

test.describe("AgentPay-IR v2 reviewer (V3 pack)", () => {
  // each test starts from an empty working store (isolation against shared-file state)
  test.beforeEach(async ({ request }) => {
    await request.post("/api/reviewer/decisions", { data: { decisions: {} } });
  });

  test("pack loads; no suggestion/hint/role/stratum/source metadata is rendered anywhere", async ({ page }) => {
    await page.goto("/reviewer");
    await expect(page.getByTestId("reviewer-root")).toBeVisible();
    const position = await page.getByTestId("reviewer-position").textContent();
    expect(Number(position)).toBeGreaterThanOrEqual(1);
    const body = (await page.content()).toLowerCase();
    for (const forbidden of [
      "label_hint", "review_role", "suggested label", "expected label",
      "stratum", "source_class", "source label",
      "_contradiction", "_entailment", "_neutral", // label-bearing metadata keys
      "gold", "supervised",
    ]) {
      expect(body, forbidden).not.toContain(forbidden);
    }
    // only card_id + premise + hypothesis are exposed per card
    const cardId = await page.locator("[data-testid=reviewer-card] p").first().textContent();
    expect(cardId?.trim()).toMatch(/^rc2_\d{4}$/);
  });

  test("keyboard 1/2/3/4 labels, toggle, prev/next, progress", async ({ page }) => {
    await page.goto("/reviewer");
    await expect(page.getByTestId("reviewer-premise")).not.toBeEmpty();
    const answered0 = Number(await page.getByTestId("reviewer-answered").textContent());

    await page.keyboard.press("1"); // contradiction on current card
    await expect(page.getByTestId("reviewer-answered")).toHaveText(String(answered0 + 1));
    await page.keyboard.press("1"); // toggle off
    await expect(page.getByTestId("reviewer-answered")).toHaveText(String(answered0));
    await page.keyboard.press("2");
    await page.keyboard.press("3");
    await page.keyboard.press("4");
    await expect(page.getByTestId("reviewer-answered")).toHaveText(String(answered0 + 1)); // last key wins, one card

    const posBefore = Number(await page.getByTestId("reviewer-position").textContent());
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId("reviewer-position")).toHaveText(String(posBefore + 1));
    await page.keyboard.press("ArrowLeft");
    await expect(page.getByTestId("reviewer-position")).toHaveText(String(posBefore));
    await page.keyboard.press("ArrowLeft"); // clamp at first card
    await expect(page.getByTestId("reviewer-position")).toHaveText(String(Math.max(1, posBefore - 1)));
  });

  test("autosave survives reload and export is deterministic", async ({ page }) => {
    await page.goto("/reviewer");
    await expect(page.getByTestId("reviewer-premise")).not.toBeEmpty();
    await page.keyboard.press("3"); // neutral on card 1
    await expect(page.getByTestId("reviewer-savestate")).toHaveText("saved", { timeout: 5000 });

    await page.reload();
    await expect(page.getByTestId("reviewer-premise")).not.toBeEmpty();
    await expect(page.getByTestId("label-neutral")).toHaveClass(/selected/);
    await page.keyboard.press("3"); // clear it again to keep the working store minimal
    await expect(page.getByTestId("reviewer-savestate")).toHaveText("saved", { timeout: 5000 });

    // deterministic export: two consecutive fetches are byte-identical and parse to the saved rows
    const export1 = await page.request.get("/api/reviewer/export");
    const text1 = await export1.text();
    const export2 = await page.request.get("/api/reviewer/export");
    expect(await export2.text()).toBe(text1);
    const parsed = JSON.parse(text1) as { export_version: number; rows: { card_id: string; decision: string }[] };
    expect(parsed.export_version).toBe(1);
    const ids = parsed.rows.map((r) => r.card_id);
    expect([...ids].sort()).toEqual(ids); // sorted by card_id
    for (const r of parsed.rows) {
      expect(DECISIONS).toContain(r.decision as (typeof DECISIONS)[number]);
    }
  });
});
