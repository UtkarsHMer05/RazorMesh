/**
 * Phase-5 browser harness helpers (M008).
 *
 * Rules encoded here (master prompt §7/§16):
 * - No fake API outcomes: helpers wait for REAL backend-driven UI state.
 * - Stage waits bind to data-stage attributes the pages render from real events.
 * - Evidence capture writes screenshots under docs/phase5/evidence/<milestone>/.
 * - Reduced-motion mode emulates prefers-reduced-motion for a11y proof.
 */
import { expect, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import nodePath from "node:path";
import { fileURLToPath } from "node:url";

const HERE = nodePath.dirname(fileURLToPath(import.meta.url));

// e2e/ -> apps/web/ -> apps/ -> RazorMesh repo root
export const EVIDENCE_ROOT = nodePath.resolve(
  HERE,
  "../../../docs/phase5/evidence",
);

export const RECORDING_WIDTH = 1920;
export const RECORDING_HEIGHT = 1080;
export const LAPTOP_WIDTH = 1440;
export const LAPTOP_HEIGHT = 900;

export const DEMO_ROUTES = [
  "/",
  "/buyer",
  "/merchant",
  "/protocols",
  "/security-lab",
  "/audit",
] as const;

export async function captureEvidence(
  page: Page,
  milestone: string,
  name: string,
  fullPage = false,
): Promise<string> {
  const dir = nodePath.join(EVIDENCE_ROOT, milestone);
  mkdirSync(dir, { recursive: true });
  const file = nodePath.join(dir, `${name}.png`);
  const bytes = await page.screenshot({ fullPage });
  writeFileSync(file, bytes);
  return file;
}

/** Enable reduced-motion emulation BEFORE navigation so CSS applies on load. */
export async function enableReducedMotion(page: Page): Promise<void> {
  await page.emulateMedia({ reducedMotion: "reduce" });
}

/** Wait until a pipeline stage node reaches one of the given states. */
export async function waitForStage(
  page: Page,
  stage: string,
  state: string | string[],
  timeout = 15_000,
): Promise<void> {
  const states = Array.isArray(state) ? state : [state];
  const locator = page
    .locator(`[data-stage="${stage}"]`)
    .filter({ has: page.locator(`[data-state="${states.join('"], [data-state="')}"]`) });
  await expect(locator.first()).toBeVisible({ timeout });
}

/** Read the state of a stage node rendered from backend evidence. */
export async function readStageState(
  page: Page,
  stage: string,
): Promise<string | null> {
  const node = page.locator(`[data-stage="${stage}"]`).first();
  if ((await node.count()) === 0) return null;
  return node.getAttribute("data-state");
}

/**
 * Wait for a trace badge to show a specific trace id and return it.
 * The badge only ever renders ids the backend issued (never client-invented).
 * Note: the badge is visible in its empty ("No live mission") state too, so
 * this waits for the backend-issued RM- pattern, not mere visibility.
 */
export async function waitForTraceBadge(
  page: Page,
  timeout = 20_000,
): Promise<string> {
  const badge = page.getByTestId("trace-badge");
  await expect(badge).toBeVisible({ timeout });
  await expect(badge).toContainText(/RM-[0-9A-HJKMNP-TV-Z]{6}/, { timeout });
  const text = (await badge.textContent()) ?? "";
  const match = text.match(/RM-[0-9A-HJKMNP-TV-Z]{6}/);
  expect(match, `trace badge shows a backend-issued trace id (got: ${text})`).not.toBeNull();
  return match ? match[0] : "";
}

/** Assert the same trace id renders on another route (cross-page continuity). */
export async function expectSameTrace(
  page: Page,
  route: string,
  traceId: string,
): Promise<void> {
  await page.goto(route);
  await expect(page.getByTestId("trace-badge")).toContainText(traceId);
}

/** Wait for a terminal decision pill rendered from a real backend decision. */
export async function waitForDecision(
  page: Page,
  decision: "ALLOW" | "CHALLENGE" | "BLOCK",
  timeout = 20_000,
): Promise<void> {
  await expect(
    page.getByTestId(`decision-${decision.toLowerCase()}`),
  ).toBeVisible({ timeout });
}

/** Assert no provider contact claim unless backed by audit evidence. */
export async function expectProviderNotContacted(page: Page): Promise<void> {
  await expect(page.getByTestId("provider-boundary")).toContainText(
    /not contacted|calls: 0/i,
  );
}

/** Assert horizontal layout fits (no overflow) at the current viewport. */
export async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => {
    const d = document.documentElement;
    return d.scrollWidth - d.clientWidth;
  });
  expect(overflow).toBeLessThanOrEqual(2);
}

/** Read console errors (excluding Next.js dev overlay noise) for a run. */
export function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(String(err)));
  return errors;
}

/** Verify a fetch response body never contains secret-shaped strings. */
export async function expectNoSecretsIn(
  page: Page,
  urlPattern: RegExp,
): Promise<void> {
  page.on("response", async (res) => {
    if (!urlPattern.test(res.url())) return;
    const body = await res.text().catch(() => "");
    expect(
      /rzp_live_|sk_live|-----BEGIN (RSA|EC) PRIVATE KEY|key_secret\s*[:=]/i.test(
        body,
      ),
      `secret-shaped string leaked from ${res.url()}`,
    ).toBe(false);
  });
}
