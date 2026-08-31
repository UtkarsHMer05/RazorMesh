import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import BuyerPage from "./page";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/**
 * P3-M17 invariants, ported to the Phase-5 Buyer mission flow (M019–M024):
 * proposal-only framing, human confirmation as the only authority gate, and
 * no confirmation offered while clarification is required.
 */

function draftBody(overrides: Record<string, unknown> = {}) {
  return {
    draft_id: "drf_test",
    state: "DRAFT",
    payload: {
      hard: { max_amount: { amount_minor: 500000, currency: "INR" } },
      semantic_constraints: [],
      ambiguities: [],
      unspecified: [{ field: "merchant" }],
    },
    compiler_model: "fixture-qwen",
    prompt_version: "prompt-v2",
    superseded_by: null,
    intent_id: null,
    confirmed_generation: null,
    ...overrides,
  };
}

describe("P3-M17 invariants on the Phase-5 buyer mission flow", () => {
  it("renders proposal-only framing with TEST MODE label", () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<BuyerPage />);
    const banner = screen.getByTestId("mission-banner").textContent ?? "";
    expect(banner).toContain("TEST MODE");
    expect(banner).toContain("never by this UI");
    expect(screen.getByText(/nothing\s+becomes authority until you confirm/i)).toBeTruthy();
    expect(screen.getByTestId("compile-btn")).toBeDisabled(); // empty mandate
  });

  it("shows the structured proposal before a human can confirm it", async () => {
    // Route-aware mock: fixture-intent (mount) -> compile -> confirm.
    // Catalog + trace lookups fail harmlessly (the page is defensive).
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      const u = String(url);
      if (u.includes("/buyer/fixture-intent")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ intent_id: "intent_01M19X68VHHBGW00H2CFB13KFM" }),
        });
      }
      if (u.includes("/intent-drafts/compile")) {
        return Promise.resolve({ ok: true, json: async () => draftBody() });
      }
      if (u.includes("/intent-drafts/") && u.includes("/confirm")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            draft_id: "drf_test",
            state: "CONFIRMED",
            intent_id: "intent_01M19X68VHHBGW00H2CFB13KFM",
            generation: 1,
            replayed: false,
          }),
        });
      }
      return Promise.resolve({ ok: false, json: async () => ({}) });
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", {
      randomUUID: () => "00000000-0000-4000-8000-000000000001",
      getRandomValues: (arr: Uint8Array) => arr.fill(1),
    });

    render(<BuyerPage />);
    fireEvent.change(screen.getByTestId("nl-input"), {
      target: { value: "Buy headphones under 5000 rupees" },
    });
    fireEvent.click(screen.getByTestId("compile-btn"));

    // Constraint cards render the real draft payload.
    expect(await screen.findByTestId("draft-state")).toHaveTextContent("DRAFT");
    expect(screen.getByTestId("draft-hard").textContent).toContain("500000");
    expect(screen.getByTestId("draft-unspecified")).toHaveTextContent("merchant");
    expect(screen.getByTestId("confirm-draft")).toBeEnabled();
    // No authority-granted ceremony before confirmation.
    expect(screen.queryByText(/AUTHORITY GRANTED/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("confirm-draft"));
    await waitFor(() =>
      expect(screen.getByText(/AUTHORITY GRANTED/)).toBeInTheDocument(),
    );
  });

  it("does not offer confirmation while clarification is required", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () =>
          draftBody({
            state: "NEEDS_CLARIFICATION",
            payload: {
              hard: {},
              semantic_constraints: [],
              ambiguities: [{ question: "Which currency?" }],
            },
          }),
      }),
    );
    vi.stubGlobal("crypto", {
      randomUUID: () => "00000000-0000-4000-8000-000000000002",
      getRandomValues: (arr: Uint8Array) => arr.fill(2),
    });

    render(<BuyerPage />);
    fireEvent.change(screen.getByTestId("nl-input"), { target: { value: "Buy headphones" } });
    fireEvent.click(screen.getByTestId("compile-btn"));

    expect(await screen.findByTestId("clarify-note")).toBeInTheDocument();
    expect(screen.queryByTestId("confirm-draft")).not.toBeInTheDocument();
  });
});
