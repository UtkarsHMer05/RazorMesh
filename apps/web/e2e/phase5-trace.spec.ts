/**
 * Phase-5 (M012–M016): live-trace continuity + deep links + Start New Mission.
 * Runs against the real backend; trace ids must be backend-issued only.
 */
import { expect, test } from "@playwright/test";
import { captureEvidence, waitForTraceBadge } from "./phase5-helpers";

test("buyer mints a backend trace and the badge shows it everywhere", async ({ page }) => {
  await page.goto("/buyer");
  const traceId = await waitForTraceBadge(page);
  await expect(page.getByTestId("mission-trace")).toContainText(traceId);

  for (const route of ["/merchant", "/protocols", "/security-lab", "/audit"]) {
    await page.goto(route);
    await expect(page.getByTestId("trace-badge")).toContainText(traceId);
  }

  await page.reload();
  await expect(page.getByTestId("trace-badge")).toContainText(traceId);
  await captureEvidence(page, "m012-m016", "trace-continuity");
});

test("deep link ?trace= loads the exact trace without in-memory state", async ({ page }) => {
  await page.goto("/buyer");
  const traceId = await waitForTraceBadge(page);
  // Simulate a copied link opened in a fresh context state.
  await page.goto(`/audit?trace=${traceId}`);
  await expect(page.getByTestId("trace-badge")).toContainText(traceId);
});

test("Start New Mission creates a distinct trace; old trace stays searchable", async ({
  page,
}) => {
  await page.goto("/buyer");
  await page.waitForTimeout(2500); // fixture intent auto-creation
  const first = await waitForTraceBadge(page);

  await page.getByTestId("start-new-mission").click();
  await page.waitForTimeout(2500);
  const second = await waitForTraceBadge(page);
  expect(second).not.toBe(first);

  // Old trace still resolves from backend evidence (audit history preserved).
  const res = await page.request.get(`/api/trace/${first}`);
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  expect(body.trace.trace_id).toBe(first);

  // Invalid/malformed trace ids never resolve.
  const bad = await page.request.get(`/api/trace/rm-fake1`);
  expect(bad.status()).toBe(404);
  await captureEvidence(page, "m012-m016", "start-new-mission");
});

test("trace API responses never contain secret-shaped strings", async ({ page }) => {
  await page.goto("/buyer");
  const traceId = await waitForTraceBadge(page);
  for (const path of [
    `/api/trace/${traceId}`,
    `/api/trace/${traceId}/events`,
    "/api/trace/recent",
  ]) {
    const res = await page.request.get(path);
    expect(res.ok()).toBeTruthy();
    const body = await res.text();
    expect(
      /rzp_live_|sk_live|BEGIN (RSA|EC) PRIVATE KEY|key_secret/i.test(body),
      `secret-shaped string in ${path}`,
    ).toBe(false);
  }
});
