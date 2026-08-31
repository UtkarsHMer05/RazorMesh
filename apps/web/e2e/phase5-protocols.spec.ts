/**
 * Phase-5 (M046–M062): Protocol Playground e2e.
 * Real backend only — every assertion reads engine-derived results.
 */
import { expect, test } from "@playwright/test";

test("playground shows the authority thesis and supported transports", async ({ page }) => {
  await page.goto("/protocols");
  await expect(page.getByTestId("protocol-thesis")).toContainText(
    /protocol validity is not transaction authority/i,
  );
  for (const p of ["mcp", "ucp", "ap2", "acp", "a2a"]) {
    await expect(page.getByTestId(`protocol-${p}`)).toBeVisible();
  }
});

test("safe packet passes protocol checks with MATCH commitment", async ({ page }) => {
  await page.goto("/protocols");
  await page.getByTestId("protocol-ucp").click();
  await page.getByTestId("mutation-select").selectOption("none");
  await page.getByTestId("send-packet").click();
  await expect(page.getByTestId("gateway-checks")).toContainText("PROTOCOL_PASS", {
    timeout: 10_000,
  });
  await page.waitForTimeout(1600); // let the ordered reveal finish
  await expect(page.getByTestId("gateway-checks")).toContainText("MATCH");
  await expect(page.getByTestId("authority-bridge")).toContainText(
    /never authorizes payment/i,
  );
});

test("amount drift passes protocol but MISMATCHes the commitment (the thesis)", async ({
  page,
}) => {
  await page.goto("/protocols");
  await page.getByTestId("protocol-mcp").click();
  await page.getByTestId("mutation-select").selectOption("amount_plus_one");
  await page.getByTestId("send-packet").click();
  const checks = page.getByTestId("gateway-checks");
  await expect(checks).toContainText("PROTOCOL_PASS", { timeout: 10_000 });
  await page.waitForTimeout(1600);
  await expect(checks).toContainText("MISMATCH");
});

test("replay and downgrade are rejected by the real engines", async ({ page }) => {
  await page.goto("/protocols");
  await page.getByTestId("protocol-ap2").click();
  await page.getByTestId("mutation-select").selectOption("replay_same_packet");
  await page.getByTestId("send-packet").click();
  await expect(page.getByTestId("gateway-checks")).toContainText("FAIL", { timeout: 10_000 });

  await page.getByTestId("protocol-mcp").click();
  await page.getByTestId("mutation-select").selectOption("protocol_downgrade");
  await page.getByTestId("send-packet").click();
  const checks = page.getByTestId("gateway-checks");
  await expect(checks).toContainText("PROTOCOL_BLOCK", { timeout: 10_000 });
  await page.waitForTimeout(1600);
  await expect(checks).toContainText("FAIL");
});

test("cross-protocol divergence isolates exactly one lane", async ({ page }) => {
  await page.goto("/protocols");
  const laneState = async (proto: string) =>
    page.getByTestId(`lane-${proto}`).getAttribute("data-state");

  // All lanes true first.
  await expect(page.getByTestId("cross-overall")).toContainText("MATCH", { timeout: 10_000 });
  for (const p of ["mcp", "ucp", "ap2", "acp", "a2a"]) {
    await expect(await laneState(p)).toBe("MATCH");
  }

  // Diverge AP2: only that lane mismatches.
  await page.getByTestId("diverge-ap2").click();
  await expect(page.getByTestId("cross-overall")).toContainText("MISMATCH", {
    timeout: 10_000,
  });
  await expect(await laneState("ap2")).toBe("MISMATCH");
  for (const p of ["mcp", "ucp", "acp", "a2a"]) {
    await expect(await laneState(p)).toBe("MATCH");
  }
});

test("no key material appears anywhere on the page", async ({ page }) => {
  await page.goto("/protocols");
  await page.getByTestId("send-packet").click();
  await page.waitForTimeout(2000);
  const content = await page.content();
  expect(content).not.toMatch(/BEGIN (RSA |EC )?PRIVATE KEY|rzp_secret|signature_hex/);
});
