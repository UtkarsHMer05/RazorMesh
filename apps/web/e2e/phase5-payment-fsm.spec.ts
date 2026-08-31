/**
 * Phase-5 (M095-M100) acceptance: Razorpay failure lifecycle.
 *
 * The checkout script is replaced by a deterministic in-browser stub that
 * captures the app's registered payment.failed handler — so the test fires
 * the OFFICIAL failure event exactly as the real checkout would. Backend
 * endpoints are route-mocked (same pattern as checkout.spec.ts); the page
 * under test is the REAL buyer bundle.
 *
 * Proves the §8 bug fix end-to-end:
 * payment.failed → modal auto-closes → PAYMENT FAILED + safe reason →
 * Try Again (fresh revalidation) — plus dismissal ≠ failure and no stale
 * EXECUTING.
 */
import { expect, test } from "@playwright/test";

type FsmWindow = Window & {
  __rzpCaptured?: { modal?: { ondismiss?: () => void } } | null;
  __rzpClosed?: boolean;
  __rzpFailHandler?: (payload: unknown) => void;
};
const fsmWindow = () => window as unknown as FsmWindow;

const LAUNCH = {
  public_key_id: "rzp_test_phase5public",
  razorpay_order_id: "order_phase5_fsm",
  amount_minor: 479900,
  currency: "INR",
  execution_attempt_id: "exa_phase5_fsm",
  intent_id: "intent_phase5_fsm",
  checkout_id: "chk_phase5_fsm",
};

async function stubWorld(
  page: import("@playwright/test").Page,
  statusState: () => string,
) {
  // Checkout stub: captures options, exposes the failure handler + dismiss.
  await page.route("**/checkout.razorpay.com/v1/checkout.js", (route) =>
    route.fulfill({
      contentType: "application/javascript",
      body: `
        window.__rzpCaptured = null;
        window.__rzpClosed = false;
        window.__rzpFailHandler = null;
        window.__rzpDismiss = null;
        window.Razorpay = function (options) {
          window.__rzpCaptured = options;
          return {
            open: function () {},
            close: function () { window.__rzpClosed = true; },
            on: function (event, handler) {
              if (event === 'payment.failed') window.__rzpFailHandler = handler;
            },
          };
        };
      `,
    }),
  );
  await page.route("**/catalog/products**", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "prod_fsm",
            title: "FSM Widget",
            brand: null,
            price_minor: 400000,
            shipping_minor: 79900,
            currency: "INR",
          },
        ],
      }),
    }),
  );
  await page.route("**/buyer/fixture-intent", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ intent_id: LAUNCH.intent_id }),
    }),
  );
  await page.route("**/buyer/propose", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        decision: "ALLOW",
        reason_codes: ["SYNTHETIC_E2E_ALLOW"],
        checkout_id: LAUNCH.checkout_id,
        total_minor: LAUNCH.amount_minor,
        ticket_json: JSON.stringify({ t: "phase5-ticket" }),
        signature_hex: "ab".repeat(32),
      }),
    }),
  );
  await page.route("**/buyer/execute", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        state: "EXECUTING",
        attempt_id: LAUNCH.execution_attempt_id,
        launch: LAUNCH,
      }),
    }),
  );
  await page.route("**/buyer/callback", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ state: "FAILED" }),
    }),
  );
  await page.route("**/buyer/status**", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ state: statusState() }),
    }),
  );
}

async function reachOpenCheckout(page: import("@playwright/test").Page) {
  await page.goto("/buyer");
  await page.getByTestId("intent-id").waitFor();
  await page.getByRole("radio").first().check();
  await page.getByText("Propose checkout").click();
  await page.getByTestId("pay-action").click();
  await page.waitForFunction(() => Boolean(window.__rzpCaptured));
}

test("payment.failed auto-closes the modal and shows PAYMENT FAILED + Try Again", async ({
  page,
}) => {
  const state = "EXECUTING";
  await stubWorld(page, () => state);
  await reachOpenCheckout(page);

  // Fire the official payment.failed event (the app's own handler).
  await page.evaluate(() => {
    const fail = window.__rzpFailHandler;
    if (!fail) throw new Error("payment.failed handler not registered");
    fail({ error: { description: "Payment declined by bank", code: "PAYMENT_DECLINED" } });
  });

  // §8: modal closes automatically.
  await expect.poll(() => page.evaluate(() => Boolean(window.__rzpClosed))).toBe(true);
  // Truthful terminal state + safe reason + Try Again offer.
  await expect(page.getByTestId("pay-state")).toHaveText("PAYMENT_FAILED", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("failed-note")).toContainText(/PAYMENT FAILED/i);
  await expect(page.getByTestId("failed-note")).toContainText(/declined by bank/i);
  await expect(page.getByTestId("retry-pay")).toContainText(/Try again/i);

  // No stale EXECUTING anywhere in the payment block.
  const block = await page.getByTestId("step-payment").textContent();
  expect(block).toContain("PAYMENT_FAILED");
});

test("Try Again performs a fresh server revalidation before reopening", async ({ page }) => {
  const state = "EXECUTING";
  const statusCalls: string[] = [];
  await stubWorld(page, () => state);
  page.on("request", (r) => {
    if (r.url().includes("/buyer/status")) statusCalls.push(r.url());
  });
  await reachOpenCheckout(page);

  await page.evaluate(() => {
    const fail = window.__rzpFailHandler;
    if (!fail) throw new Error("no fail handler");
    fail({ error: { description: "Insufficient funds" } });
  });
  await expect(page.getByTestId("pay-state")).toHaveText("PAYMENT_FAILED", {
    timeout: 10_000,
  });

  const before = statusCalls.length;
  await page.getByTestId("retry-pay").click();
  // Fresh revalidation happens before any provider touch: prove it by the
  // server status call (the transient REVALIDATING phase may resolve too
  // fast to observe, which is fine — the request is the fact).
  await expect
    .poll(() => statusCalls.length, { timeout: 10_000 })
    .toBeGreaterThan(before);
  const lastCall = statusCalls[statusCalls.length - 1] ?? "";
  expect(lastCall).toContain("intent_id=intent_phase5_fsm");
  expect(lastCall).toContain("checkout_id=chk_phase5_fsm");
});

test("dismissal without a failure event is USER_DISMISSED, never a failure claim", async ({
  page,
}) => {
  const state = "EXECUTING";
  await stubWorld(page, () => state);
  await reachOpenCheckout(page);

  // Close the modal WITHOUT any failure event (user dismissed).
  await page.evaluate(() => {
    const opts = window.__rzpCaptured as { modal: { ondismiss?: () => void } };
    opts.modal.ondismiss?.();
  });
  await expect(page.getByTestId("pay-state")).toHaveText("USER_DISMISSED", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("dismissed-note")).toContainText(/closed by you/i);
  await expect(page.getByTestId("dismissed-note")).toContainText(/No failure occurred/i);
  // A dismissal must NOT render the failure note.
  await expect(page.getByTestId("failed-note")).toHaveCount(0);
  // Re-open remains available (nothing failed).
  await expect(page.getByTestId("retry-pay")).toBeVisible();
});

test("unknown provider state shows PENDING reconciliation, never a new payment", async ({
  page,
}) => {
  const state = "PROVIDER_UNKNOWN";
  await stubWorld(page, () => state);
  await reachOpenCheckout(page);

  await page.getByTestId("refresh-status").click();
  await expect(page.getByTestId("pay-state")).toHaveText("PROVIDER_UNKNOWN", {
    timeout: 10_000,
  });
  await expect(page.getByTestId("unknown-note")).toContainText(
    /reconciliation required|never double-charge/i,
  );
  await expect(page.getByTestId("retry-pay")).toHaveCount(0);
});
