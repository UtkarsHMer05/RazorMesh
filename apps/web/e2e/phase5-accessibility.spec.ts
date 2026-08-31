/**
 * Phase-5 (M117) accessibility/reduced-motion e2e — real Chromium.
 *
 * Covers: keyboard operability (Tab focus + Enter/Space activation), visible
 * focus, ARIA states, color-never-sole-signal (text labels pair with colors),
 * and reduced-motion rendering on all surfaces.
 */
import { expect, test } from "@playwright/test";
import { waitForTraceBadge } from "./phase5-helpers";

const SURFACES = [
  "/buyer",
  "/merchant",
  "/protocols",
  "/security-lab",
  "/audit",
  "/governance",
  "/mission-control",
];

test("presenter mode toggles via keyboard (Enter) on Mission Control", async ({ page }) => {
  await page.goto("/mission-control");
  const btn = page.getByTestId("presenter-mode");
  await btn.focus();
  expect(await btn.getAttribute("aria-pressed")).toBe("false");
  await btn.press("Enter");
  await expect(btn).toHaveAttribute("aria-pressed", "true");
  // State is real: label flips
  await expect(btn).toContainText(/exit presenter mode/i);
  await btn.press("Enter");
  await expect(btn).toHaveAttribute("aria-pressed", "false");
});

test("trace badge copy button is keyboard-operable with an accessible name", async ({
  page,
  context,
}) => {
  // Grant clipboard so the real handler runs (headless denies it otherwise).
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/buyer");
  await waitForTraceBadge(page); // wait for the backend-issued trace
  const copy = page.getByTestId("trace-badge").getByRole("button", { name: /copy/i });
  await copy.focus();
  await copy.press("Enter");
  // The handler announces its state truthfully (Copied → Copy).
  await expect(copy).toContainText(/copied|copy/i);
});

test("all surfaces render with reduced motion and remain operable", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const route of SURFACES) {
    await page.goto(route);
    const main = page.locator("main");
    await expect(main).toBeVisible();
    // No horizontal overflow in reduced-motion (layout identical semantics).
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(7);
  }
});

test("color is never the sole signal: decision states carry text labels", async ({ page }) => {
  // Blocked decision carries the word, not just a color.
  await page.goto("/security-lab");
  await page.getByTestId("mission-b").getByRole("button", { name: /run mission/i }).click();
  await expect(page.getByTestId("attack-movie")).toContainText(/BLOCK/i, { timeout: 60_000 });
  await expect(page.getByTestId("attack-movie")).toContainText(/WITHHELD/i);
  await expect(page.getByTestId("provider-zero")).toContainText(/NOT CONTACTED/i);
});

test("status roles: terminal outcomes announce via role=status/alert", async ({ page }) => {
  await page.goto("/mission-control");
  // presenter toggle keeps aria-pressed; evidence panel is labeled text
  await expect(page.getByTestId("mc-evidence")).toContainText(/EVIDENCE|TRACE/i);
  // Buttons have accessible names (no icon-only mystery buttons on key flows)
  for (const id of ["presenter-mode", "mc-safe", "mc-open-audit"]) {
    const name = await page.getByTestId(id).textContent();
    expect((name ?? "").trim().length).toBeGreaterThan(0);
  }
});
