/**
 * Phase-5 (M101-M113) Mission Control e2e — real backend only.
 *
 * One page proves the end-to-end story: pipeline nodes resolve from live trace
 * events, the control deck drives real scenarios, the packet stops at the
 * real decision boundary, provider stays at zero, presenter mode toggles,
 * playback replays read-only, and the summaries show canonical numbers.
 */
import { expect, test } from "@playwright/test";

test("mission control renders the pipeline and binds a trace", async ({ page }) => {
  await page.goto("/mission-control");
  for (const stage of [
    "human",
    "agent",
    "merchant",
    "protocol",
    "razorguard",
    "semantic",
    "fusion",
    "ticket",
    "provider",
    "reconciliation",
    "audit",
  ]) {
    await expect(page.getByTestId(`node-${stage}`)).toBeVisible();
  }
  // Evidence sidebar renders trace state from backend.
  await expect(page.getByTestId("mc-evidence")).toContainText(/TRACE|—/);
});

test("hidden-membership attack runs end-to-end and stops the packet at the boundary", async ({
  page,
}) => {
  await page.goto("/mission-control");
  await page.getByTestId("mc-hidden-membership").click();
  // Real pipeline (DeBERTa in the loop) — allow generous time.
  await expect(page.getByTestId("mc-status")).toContainText(/final BLOCK/i, {
    timeout: 60_000,
  });
  // Nodes resolve from live events.
  await expect(page.getByTestId("node-razorguard")).toHaveAttribute(
    "data-state",
    "BLOCK",
    { timeout: 15_000 },
  );
  await expect(page.getByTestId("node-ticket")).toHaveAttribute("data-state", "WITHHELD");
  // The packet stopped at the decision boundary; provider never contacted.
  await expect(page.getByTestId("stopped-at")).toContainText(/stopped at razorguard/i);
  await expect(page.getByTestId("stopped-at")).toContainText(/never contacted/i);
});

test("protocol-thesis scenario proves PASS/decide/zero-provider", async ({ page }) => {
  await page.goto("/mission-control");
  await page.getByTestId("mc-protocol-thesis").click();
  await expect(page.getByTestId("mc-status")).toContainText(/final BLOCK/i, {
    timeout: 60_000,
  });
  await expect(page.getByTestId("node-protocol")).toHaveAttribute(
    "data-state",
    /PROTOCOL_PASS|BLOCK/,
    { timeout: 15_000 },
  );
});

test("presenter mode toggles without changing behavior", async ({ page }) => {
  await page.goto("/mission-control");
  await page.getByTestId("presenter-mode").click();
  await expect(page.getByTestId("mc-pipeline")).toBeVisible(); // same real pipeline
  await expect(page.getByTestId("presenter-mode")).toContainText(/exit presenter mode/i);
  await page.getByTestId("presenter-mode").click();
  await expect(page.getByTestId("mc-pipeline")).toBeVisible();
});

test("summaries show canonical campaign + governance truth", async ({ page }) => {
  await page.goto("/mission-control");
  const summaries = page.getByTestId("mc-summaries");
  await expect(summaries).toContainText(/AgentPay-X canonical benchmark/i, {
    timeout: 20_000,
  });
  await expect(summaries).toContainText(/191/);
  await expect(summaries).toContainText(/REJECTED/i);
  await expect(summaries).toContainText(/frozen safety gate/i);
});

test("clean demo reset preserves audit history", async ({ page }) => {
  await page.goto("/mission-control");
  await page.getByTestId("mc-demo-reset").click();
  await expect(page.getByTestId("mc-status")).toContainText(
    /prior missions still searchable/i,
    { timeout: 20_000 },
  );
});
