import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import BuyerPage from "@/app/buyer/page";

// The checkout loader is proven separately (razorpay.test.ts); here the modal
// lifecycle is driven directly through the captured constructor options.
vi.mock("@/lib/razorpay", () => ({
  loadRazorpayCheckout: vi.fn(async () => true),
}));

type CapturedOptions = {
  handler: (response: Record<string, string>) => void;
  modal: { confirm_close: boolean; ondismiss?: () => void };
};

let captured: CapturedOptions | null = null;
let statusResponse: Record<string, unknown> = { state: "EXECUTING" };

const LAUNCH = {
  public_key_id: "rzp_test_public",
  razorpay_order_id: "order_ui_sync_1",
  amount_minor: 479900,
  currency: "INR",
  execution_attempt_id: "exa_ui_sync_1",
  intent_id: "intent_ui_sync_1",
  checkout_id: "chk_ui_sync_1",
};

function mockFetch() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const json = (body: unknown) =>
      new Response(JSON.stringify(body), { status: 200 });
    if (url.includes("/catalog/products")) {
      return json({
        items: [
          {
            id: "prod_ui_sync_1",
            title: "Sync Widget",
            brand: null,
            price_minor: 400000,
            shipping_minor: 79900,
            currency: "INR",
          },
        ],
      });
    }
    if (url.includes("/buyer/fixture-intent")) return json({ intent_id: "intent_ui_sync_1" });
    if (url.includes("/buyer/propose")) {
      return json({
        decision: "ALLOW",
        reason_codes: [],
        checkout_id: "chk_ui_sync_1",
        total_minor: 479900,
        ticket_json: JSON.stringify({ t: "ui-sync-ticket" }),
        signature_hex: "ab".repeat(32),
      });
    }
    if (url.includes("/buyer/execute")) {
      return json({ state: "EXECUTING", attempt_id: "exa_ui_sync_1", launch: LAUNCH });
    }
    if (url.includes("/buyer/status")) return json(statusResponse);
    throw new Error(`unexpected fetch in test: ${url}`);
  });
}

async function reachCheckoutPhase(fetchMock: ReturnType<typeof mockFetch>) {
  vi.stubGlobal("fetch", fetchMock);
  captured = null;
  class FakeRz {
    constructor(options: CapturedOptions) {
      captured = options;
    }
    open() {}
  }
  (window as unknown as { Razorpay?: unknown }).Razorpay = FakeRz;

  render(<BuyerPage />);
  await screen.findByTestId("product-list");
  fireEvent.click(screen.getByText("Create fixture authorization"));
  await screen.findByTestId("intent-id");
  fireEvent.click(screen.getAllByRole("radio")[0]);
  fireEvent.click(screen.getByText("Propose checkout"));
  await screen.findByTestId("decision-banner");
  fireEvent.click(screen.getByTestId("pay-action"));
  await screen.findByTestId("launch-summary");
  await waitFor(() => expect(captured).not.toBeNull());
}

describe("P2-M40: buyer UI re-syncs payment truth from the server", () => {
  beforeEach(() => {
    statusResponse = { state: "EXECUTING" };
  });

  afterEach(() => {
    // vitest globals are disabled, so RTL does not auto-unmount between tests.
    cleanup();
    vi.unstubAllGlobals();
  });

  it("modal dismiss shows FAILED when the webhook already settled the attempt", async () => {
    const fetchMock = mockFetch();
    await reachCheckoutPhase(fetchMock);
    expect(screen.getByTestId("pay-state").textContent).toBe("EXECUTING");

    statusResponse = {
      state: "FAILED",
      attempt_id: "exa_ui_sync_1",
      fulfilment_state: "NOT_ELIGIBLE",
      razorpay_payment_status: "failed",
      error_code: "RAZORPAY_PAYMENT_FAILED",
    };
    captured?.modal.ondismiss?.();

    await waitFor(() => expect(screen.getByTestId("pay-state").textContent).toBe("FAILED"));
    expect(screen.getByTestId("failed-note")).toBeInTheDocument();
    // a dead attempt must not offer re-opening the same checkout
    expect(screen.queryByTestId("retry-pay")).toBeNull();
    expect(screen.queryByTestId("refresh-status")).toBeNull();
    const statusCalls = fetchMock.mock.calls.filter(([u]) => String(u).includes("/buyer/status"));
    expect(statusCalls.length).toBe(1);
    expect(String(statusCalls[0][0])).toContain("intent_id=intent_ui_sync_1");
    expect(String(statusCalls[0][0])).toContain("checkout_id=chk_ui_sync_1");
  });

  it("modal dismiss keeps re-open available while the server says EXECUTING", async () => {
    await reachCheckoutPhase(mockFetch());
    captured?.modal.ondismiss?.();
    await waitFor(() => expect(screen.getByTestId("pay-state").textContent).toBe("EXECUTING"));
    expect(screen.getByTestId("retry-pay")).toBeInTheDocument();
    expect(screen.getByTestId("refresh-status")).toBeInTheDocument();
    expect(screen.queryByTestId("failed-note")).toBeNull();
  });

  it("manual refresh renders server truth (SUCCEEDED) and removes payment actions", async () => {
    await reachCheckoutPhase(mockFetch());
    statusResponse = { state: "SUCCEEDED", attempt_id: "exa_ui_sync_1" };
    fireEvent.click(screen.getByTestId("refresh-status"));
    await waitFor(() =>
      expect(screen.getByTestId("pay-state").textContent).toBe("CAPTURED/PAID"),
    );
    expect(screen.queryByTestId("retry-pay")).toBeNull();
    expect(screen.queryByTestId("refresh-status")).toBeNull();
  });
});

describe("P2-M45: trust-state polish", () => {
  beforeEach(() => {
    statusResponse = { state: "EXECUTING" };
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("PROVIDER_UNKNOWN offers no payment action — refresh only", async () => {
    await reachCheckoutPhase(mockFetch());
    statusResponse = {
      state: "PROVIDER_UNKNOWN",
      attempt_id: "exa_ui_sync_1",
      error_code: "RAZORPAY_ORDER_CREATE_UNKNOWN",
    };
    fireEvent.click(screen.getByTestId("refresh-status"));
    await waitFor(() =>
      expect(screen.getByTestId("pay-state").textContent).toBe("PROVIDER_UNKNOWN"),
    );
    expect(screen.getByTestId("unknown-note")).toBeInTheDocument();
    // no payment action of any kind while the outcome is unresolved
    expect(screen.queryByTestId("retry-pay")).toBeNull();
    expect(screen.getByTestId("refresh-status")).toBeInTheDocument();
  });

  it("renders the authorization binding explanation at decision time", async () => {
    await reachCheckoutPhase(mockFetch());
    expect(screen.getByTestId("authorization-binding").textContent).toContain(
      "bound into the signed ticket",
    );
    expect(screen.getByTestId("test-mode-banner").textContent).toContain(
      "no real money",
    );
  });
});
