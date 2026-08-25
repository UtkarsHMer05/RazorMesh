import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IntentDraftPanel } from "./IntentDraftPanel";

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
});
