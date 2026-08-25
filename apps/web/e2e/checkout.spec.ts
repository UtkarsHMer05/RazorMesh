import { expect, test } from "@playwright/test";

/**
 * P2-M46: automated E2E with the external checkout boundary STUBBED.
 *
 * - The official checkout.js is replaced by a deterministic in-browser stub,
 *   so CI never touches Razorpay (real M38/M40 evidence stays the only
 *   provider-truth record).
 * - Backend endpoints are route-mocked: the page under test is the REAL
 *   buyer bundle; everything behind the API boundary is a controlled fake.
 * - Secrets (key secret / webhook secret values) must NEVER appear in the
 *   DOM or in any outgoing request URL/body. The public key id IS public by
 *   design and may appear.
 */

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    __rzpCaptured: any;
    __rzpOpened?: boolean;
  }
}

const SECRET_VALUES = ["rzp_secret_m46_value", "whsec_m46_value"] as const;

const LAUNCH = {
  public_key_id: "rzp_test_m46public",
  razorpay_order_id: "order_m46_e2e",
  amount_minor: 479900,
  currency: "INR",
  execution_attempt_id: "exa_m46_e2e",
  intent_id: "intent_m46_e2e",
  checkout_id: "chk_m46_e2e",
};

async function stubWorld(
  page: import("@playwright/test").Page,
  options: {
    executeBody?: Record<string, unknown>;
    callbackStatus?: number;
    callbackBody?: Record<string, unknown>;
    callbackRequests?: Record<string, unknown>[];
    statusState?: string;
    failCallbackNetwork?: boolean;
  } = {},
) {
  await page.route("**/checkout.razorpay.com/v1/checkout.js", (route) =>
    route.fulfill({
      contentType: "application/javascript",
      body: `
        window.__rzpCaptured = null;
        window.Razorpay = function (options) {
          window.__rzpCaptured = options;
          return { open: function () { window.__rzpOpened = true; } };
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
            id: "prod_m46",
            title: "E2E Widget",
            brand: null,
            price_minor: 400000,
            shipping_minor: 79900,
            currency: "INR",
          },
        ],
      }),
    }),
  );

  let fixtureIntentCalls = 0;
  await page.route("**/buyer/fixture-intent", (route) => {
    fixtureIntentCalls += 1;
    void fixtureIntentCalls;
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ intent_id: LAUNCH.intent_id }),
    });
  });

  await page.route("**/buyer/propose", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        decision: "ALLOW",
        reason_codes: ["SYNTHETIC_E2E_ALLOW"],
        checkout_id: LAUNCH.checkout_id,
        total_minor: LAUNCH.amount_minor,
        ticket_json: JSON.stringify({ t: "m46-ticket" }),
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
        launch: options.executeBody ?? LAUNCH,
      }),
    }),
  );

  await page.route("**/buyer/callback", (route) => {
    if (options.failCallbackNetwork) return route.abort("failed");
    options.callbackRequests?.push(
      route.request().postDataJSON() as Record<string, unknown>,
    );
    return route.fulfill({
      status: options.callbackStatus ?? 200,
      contentType: "application/json",
      body: JSON.stringify(options.callbackBody ?? { state: "EXECUTING" }),
    });
  });

  await page.route("**/buyer/status**", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ state: options.statusState ?? "EXECUTING" }),
    }),
  );
}

const SECRET_SCAN = new RegExp(SECRET_VALUES.join("|"));

async function expectNoSecrets(page: import("@playwright/test").Page) {
  const text = (await page.content()).toString();
  expect(text).not.toMatch(SECRET_SCAN);
}

test.describe("P2-M46: stubbed-checkout E2E", () => {
  test("success path: launch -> modal handler -> CAPTURED/PAID, no secrets on wire", async ({
    page,
  }) => {
    const requests: string[] = [];
    const callbackRequests: Record<string, unknown>[] = [];
    page.on("request", (r) => requests.push(`${r.method()} ${r.url()}`));

    await stubWorld(page, {
      callbackBody: { state: "SUCCEEDED" },
      callbackRequests,
    });
    await page.goto("/buyer");

    await page.getByTestId("step-catalog").waitFor();
    await page.getByText("Create fixture authorization").click();
    await page.getByRole("radio").first().check();
    await page.getByText("Propose checkout").click();
    await page.getByTestId("authorization-binding").waitFor();
    await page.getByTestId("test-mode-banner").waitFor();
    await page.getByTestId("pay-action").click();

    // The stubbed modal receives SERVER-issued fields only.
    await page.waitForFunction(() => Boolean(window.__rzpCaptured));
    const captured = (await page.evaluate(() => window.__rzpCaptured)) as Record<
      string,
      unknown
    >;
    expect(captured.order_id).toBe(LAUNCH.razorpay_order_id);
    expect(captured.amount).toBe(LAUNCH.amount_minor);
    expect(JSON.stringify(captured)).not.toMatch(SECRET_SCAN);

    // Success handler -> server verification -> CAPTURED/PAID.
    await page.evaluate((orderId: string) => {
      const opts = window.__rzpCaptured as {
        handler: (r: Record<string, string>) => void;
      };
      opts.handler({
        razorpay_payment_id: "pay_m46_ok",
        razorpay_order_id: orderId,
        razorpay_signature: "cd".repeat(32),
      });
    }, LAUNCH.razorpay_order_id);
    await expect(page.getByTestId("pay-state")).toHaveText("CAPTURED/PAID");
    expect(callbackRequests).toHaveLength(1);
    expect(callbackRequests[0]?.execution_attempt_id).toBe(
      LAUNCH.execution_attempt_id,
    );
    await expect(page.getByTestId("retry-pay")).toHaveCount(0);
    await expectNoSecrets(page);
    for (const req of requests) expect(req).not.toMatch(SECRET_SCAN);
  });

  test("failure UI: server truth renders FAILED and removes payment actions", async ({
    page,
  }) => {
    await stubWorld(page, {
      callbackBody: { state: "FAILED" },
    });
    await page.goto("/buyer");
    await page.getByText("Create fixture authorization").click();
    await page.getByRole("radio").first().check();
    await page.getByText("Propose checkout").click();
    await page.getByTestId("pay-action").click();

    await page.waitForFunction(() => Boolean(window.__rzpCaptured));
    await page.evaluate((orderId: string) => {
      const opts = window.__rzpCaptured as {
        handler: (r: Record<string, string>) => void;
      };
      opts.handler({
        razorpay_payment_id: "pay_m46_fail",
        razorpay_order_id: orderId,
        razorpay_signature: "ee".repeat(32),
      });
    }, LAUNCH.razorpay_order_id);
    await expect(page.getByTestId("pay-state")).toHaveText("FAILED");
    await expect(page.getByTestId("failed-note")).toBeVisible();
    await expect(page.getByTestId("retry-pay")).toHaveCount(0);
    await expectNoSecrets(page);
  });

  test("unknown state: network failure during verification offers refresh only", async ({
    page,
  }) => {
    await stubWorld(page, { failCallbackNetwork: true, statusState: "PROVIDER_UNKNOWN" });
    await page.goto("/buyer");
    await page.getByText("Create fixture authorization").click();
    await page.getByRole("radio").first().check();
    await page.getByText("Propose checkout").click();
    await page.getByTestId("pay-action").click();

    await page.waitForFunction(() => Boolean(window.__rzpCaptured));
    await page.evaluate((orderId: string) => {
      const opts = window.__rzpCaptured as {
        handler: (r: Record<string, string>) => void;
      };
      opts.handler({
        razorpay_payment_id: "pay_m46_unk",
        razorpay_order_id: orderId,
        razorpay_signature: "ff".repeat(32),
      });
    }, LAUNCH.razorpay_order_id);
    await expect(page.getByTestId("pay-state")).toHaveText("PROVIDER_UNKNOWN");
    await expect(page.getByTestId("unknown-note")).toContainText(
      /starting a NEW payment is intentionally unavailable/i,
    );
    await expect(page.getByTestId("refresh-status")).toBeVisible();
    await expect(page.getByTestId("retry-pay")).toHaveCount(0);
    await expectNoSecrets(page);
  });
});
