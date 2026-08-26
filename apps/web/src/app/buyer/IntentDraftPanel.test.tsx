import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IntentDraftPanel } from "./IntentDraftPanel";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("P3-M17: intent draft panel", () => {
  it("renders proposal-only framing with TEST MODE label", () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<IntentDraftPanel />);
    expect(screen.getByTestId("intent-draft-panel").textContent).toContain(
      "nothing becomes authority until you confirm it",
    );
    expect(screen.getByTestId("intent-draft-panel").textContent).toContain(
      "TEST MODE",
    );
    expect(screen.getByTestId("compile-btn")).toBeDisabled(); // empty input
  });

  it("shows the structured proposal before a human can confirm it", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
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
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          draft_id: "drf_test",
          state: "CONFIRMED",
          intent_id: "int_test",
          generation: 1,
          replayed: false,
        }),
      });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("crypto", { randomUUID: () => "00000000-0000-4000-8000-000000000001" });

    render(<IntentDraftPanel />);
    fireEvent.change(screen.getByTestId("nl-input"), {
      target: { value: "Buy headphones under 5000 rupees" },
    });
    fireEvent.click(screen.getByTestId("compile-btn"));

    await screen.findByText(/State:/);
    expect(screen.getByTestId("draft-hard").textContent).toContain("500000");
    expect(screen.getByTestId("draft-unspecified")).toHaveTextContent("merchant");
    expect(screen.getByTestId("confirm-draft")).toBeEnabled();
    expect(screen.queryByTestId("confirmed-note")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("confirm-draft"));
    await waitFor(() => expect(screen.getByTestId("draft-state")).toHaveTextContent("CONFIRMED"));
    expect(screen.getAllByTestId("confirmed-note")).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not offer confirmation while clarification is required", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          draft_id: "drf_needs_clarification",
          state: "NEEDS_CLARIFICATION",
          payload: {
            hard: {},
            semantic_constraints: [],
            ambiguities: [{ question: "Which currency?" }],
          },
          compiler_model: "fixture-qwen",
          prompt_version: "prompt-v2",
          superseded_by: null,
          intent_id: null,
          confirmed_generation: null,
        }),
      }),
    );
    vi.stubGlobal("crypto", { randomUUID: () => "00000000-0000-4000-8000-000000000002" });

    render(<IntentDraftPanel />);
    fireEvent.change(screen.getByTestId("nl-input"), { target: { value: "Buy headphones" } });
    fireEvent.click(screen.getByTestId("compile-btn"));

    expect(await screen.findByTestId("clarify-note")).toBeInTheDocument();
    expect(screen.queryByTestId("confirm-draft")).not.toBeInTheDocument();
  });
});
