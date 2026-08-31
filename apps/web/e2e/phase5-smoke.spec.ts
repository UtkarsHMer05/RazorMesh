/**
 * Phase-5 baseline navigation smoke (M008).
 * Proves the harness reaches every demo route against the real backend,
 * with no console errors and no horizontal overflow at recording width.
 */
import { expect, test } from "@playwright/test";
import {
  DEMO_ROUTES,
  RECORDING_HEIGHT,
  RECORDING_WIDTH,
  collectConsoleErrors,
  expectNoHorizontalOverflow,
} from "./phase5-helpers";

test.describe("phase-5 harness reaches all demo surfaces", () => {
  for (const route of DEMO_ROUTES) {
    test(`navigates ${route} at recording width`, async ({ page }) => {
      const errors = collectConsoleErrors(page);
      await page.setViewportSize({
        width: RECORDING_WIDTH,
        height: RECORDING_HEIGHT,
      });
      await page.goto(route);
      await expect(page).toHaveTitle(/RazorMesh Trust/i);
      await expect(page.locator("main")).toBeVisible();
      await expectNoHorizontalOverflow(page);
      // Filter out Next.js dev overlay noise; real page errors must be zero.
      const real = errors.filter(
        (e) => !/next_dev_tools|Download the React DevTools/i.test(e),
      );
      expect(real, `console errors on ${route}`).toEqual([]);
    });
  }

  test("reduced-motion mode still renders all routes", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    for (const route of DEMO_ROUTES) {
      await page.goto(route);
      await expect(page.locator("main")).toBeVisible();
    }
  });
});
