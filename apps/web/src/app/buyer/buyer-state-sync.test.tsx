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
    // Phase-5 additions (trace registry / agent search) are non-authoritative
    // for these lifecycle tests; answer harmlessly instead of throwing.
    if (url.includes("/api/trace/")) return json({ trace_id: "RM-TEST00", events: [] });
    if (url.includes("/api/agent/search")) {
      return json({ inspected: 1, eligible: 1, rejected: 0, candidates: [], rejected_samples: [] });
    }
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
  // The fixture intent is auto-created on mount; wait for intent-id to appear.
  // If the test environment pre-populates intentId, this is a no-op.
  try {
    const btn = screen.queryByText("Create fixture authorization");
    if (btn) fireEvent.click(btn);
  } catch {
    // already created
  }
  await screen.findByTestId("intent-id");
  fireEvent.click(screen.getAllByRole("radio")[0]);
  fireEvent.click(screen.getByText("Propose checkout"));
  await screen.findByTestId("decision-outcome");
  fireEvent.click(screen.getByTestId("pay-action"));
  await screen.findByTestId("launch-summary");
  await waitFor(() => expect(captured).not.toBeNull());
}

describe("P3-M17: AI draft budget filters products", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("confirmed draft max_amount hides products above the budget", async () => {
    const fetchMock = vi
      .fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });
        if (url.includes("/catalog/products")) {
          return json({
            items: [
              { id: "p_cheap", title: "Cheap headphones", brand: null, price_minor: 300000, shipping_minor: 0, currency: "INR" },
              { id: "p_expensive", title: "Expensive headphones", brand: null, price_minor: 700000, shipping_minor: 0, currency: "INR" },
            ],
          });
        }
        if (url.includes("/buyer/fixture-intent")) return json({ intent_id: "intent_test" });
        if (url.includes("/compile")) {
          return json({
            draft_id: "drf_test",
            state: "DRAFT",
            payload: {
              product_summary: "headphones",
              hard: { max_amount: { amount_minor: 500000, currency: "INR" } },
              ambiguities: [],
              unspecified: [],
            },
            compiler_model: "test",
            prompt_version: "v1",
            superseded_by: null,
            intent_id: null,
            confirmed_generation: null,
          });
        }
        if (url.includes("/confirm"))
          return json({
            draft_id: "drf_test",
            state: "CONFIRMED",
            intent_id: "intent_test",
            generation: 1,
            replayed: false,
          });
        if (url.includes("/api/agent/search")) {
          // Real backend semantics: the 700000-minor product exceeds the
          // confirmed 500000 budget and must come back rejected.
          return json({
            inspected: 2,
            eligible: 1,
            rejected: 1,
            candidates: [
              {
                product_id: "p_cheap",
                title: "Cheap headphones",
                brand: null,
                category: "audio",
                condition: "new",
                merchant_id: "mrc_test",
                unit_price_minor: 300000,
                shipping_minor: 0,
                quantity: 1,
                total_minor: 300000,
                currency: "INR",
                score: -300000,
                rank: 1,
                why: ["All-in total ₹3,000.00 ≤ confirmed budget ₹5,000.00"],
                recurring: false,
              },
            ],
            rejected_samples: [
              {
                product_id: "p_expensive",
                title: "Expensive headphones",
                reason_code: "TOTAL_EXCEEDS_BUDGET",
                explanation:
                  "All-in total ₹7,000.00 exceeds the confirmed all-in budget ₹5,000.00.",
              },
            ],
          });
        }
        if (url.includes("/api/trace/")) return json({ trace_id: "RM-TEST00", events: [] });
        throw new Error(`unexpected: ${url}`);
      });

    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", {
      randomUUID: () => "00000000-0000-4000-8000-000000000001",
      getRandomValues: (arr: Uint8Array) => arr.fill(1),
    });

    render(<BuyerPage />);
    await screen.findByTestId("intent-id");

    // Compile and confirm the draft with a 5000-rupee budget
    await screen.findByTestId("nl-input");
    fireEvent.change(screen.getByTestId("nl-input"), { target: { value: "Buy headphones under 5000 rupees" } });
    fireEvent.click(screen.getByTestId("compile-btn"));
    await screen.findByTestId("draft-view");
    fireEvent.click(screen.getByTestId("confirm-draft"));
    await waitFor(() => expect(screen.getByTestId("confirmed-note")).toBeInTheDocument());

    // The agent search (server-authoritative) proposes only the in-budget
    // product; the over-budget product is rejected with the exact reason.
    const candidates = await screen.findAllByTestId(/^candidate-\d+$/);
    expect(candidates).toHaveLength(1);
    expect(candidates[0].textContent).toContain("Cheap headphones");
    expect(candidates[0].textContent).toContain("All-in");
    // Rejected section exposes the over-budget product with its reason code.
    fireEvent.click(screen.getByTestId("toggle-rejected"));
    const rejected = await screen.findByTestId("rejected-candidates");
    expect(rejected.textContent).toContain("Expensive headphones");
    expect(rejected.textContent).toContain("TOTAL_EXCEEDS_BUDGET");
  });
});

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

    await waitFor(() =>
      expect(screen.getByTestId("pay-state").textContent).toBe("PAYMENT_FAILED"),
    );
    expect(screen.getByTestId("failed-note")).toBeInTheDocument();
    // a dead attempt must not offer re-opening the same checkout
    expect(screen.queryByTestId("retry-pay")).toBeNull();
    expect(screen.queryByTestId("refresh-status")).toBeNull();
    // §14 flow: openRazorpayCheckout makes one fresh-revalidation status call
    // before opening, and the dismissal makes exactly one more re-sync. The
    // dismissed call must target this attempt's ids.
    const statusCalls = fetchMock.mock.calls.filter(([u]) => String(u).includes("/buyer/status"));
    expect(statusCalls.length).toBe(2);
    expect(String(statusCalls[statusCalls.length - 1][0])).toContain("intent_id=intent_ui_sync_1");
    expect(String(statusCalls[statusCalls.length - 1][0])).toContain("checkout_id=chk_ui_sync_1");
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
