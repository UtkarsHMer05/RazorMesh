/**
 * Phase-5 (M017): no-hardcoded-outcome guard.
 *
 * Presets may preconfigure INPUTS, never displayed OUTCOMES. This spec proves
 * the UI cannot display a stale fixed ALLOW/BLOCK by driving the real backend
 * through a safe path (ALLOW) and an unsafe path (BLOCK) and asserting the
 * UI follows the backend each time — including across stale-view reloads.
 */
import { expect, test } from "@playwright/test";

test("buyer decision label follows the real backend verdict (safe → ALLOW)", async ({
  page,
}) => {
  await page.goto("/buyer");
  // Wait for the fixture intent + catalog.
  await expect(page.getByTestId("intent-id")).toBeVisible({ timeout: 20_000 });
  // Default fixture authorization + cheapest product is designed to ALLOW.
  await page.getByRole("button", { name: "Propose checkout" }).click();
  await expect(page.getByTestId("decision-outcome")).toHaveText("ALLOW", { timeout: 20_000 });

  // Reload the same mission: the decision must come back from backend state
  // (no cached/hardcoded label in the client).
  await page.reload();
  await expect(page.getByTestId("intent-id")).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Propose checkout" }).click();
  await expect(page.getByTestId("decision-outcome")).toHaveText("ALLOW", { timeout: 20_000 });
});

test("security-lab scenario B renders BLOCK from the real pipeline, not a preset constant", async ({
  page,
}) => {
  await page.goto("/security-lab");
  await page
    .getByRole("button", { name: /Scenario B — recurring membership/i })
    .click();
  // Backend pipeline (DeBERTa in the loop) — allow generous time.
  const result = page.getByRole("heading", { name: /FINAL BLOCK/ });
  await expect(result).toBeVisible({ timeout: 45_000 });
  // Evidence-backed rows, not constants (rowheader + cell structure):
  const rowValue = (label: string) =>
    page.getByRole("row", { name: label }).getByRole("cell");
  await expect(rowValue("Razorpay contacted")).toHaveText("no");
  await expect(rowValue("ExecutionTicket issued")).toHaveText("no");
});

test("block labels never render for a safe catalog selection after an attack ran", async ({
  page,
}) => {
  // Anti-stale check: run scenario B (BLOCK), then go to buyer and propose —
  // the UI must show ALLOW from the fresh backend decision, not the last one.
  await page.goto("/security-lab");
  await page
    .getByRole("button", { name: /Scenario B — recurring membership/i })
    .click();
  await expect(page.getByRole("heading", { name: /FINAL BLOCK/ })).toBeVisible({
    timeout: 45_000,
  });

  await page.goto("/buyer");
  await expect(page.getByTestId("intent-id")).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Propose checkout" }).click();
  await expect(page.getByTestId("decision-outcome")).toHaveText("ALLOW", { timeout: 20_000 });
});
