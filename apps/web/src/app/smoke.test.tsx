import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "@/app/page";
import BuyerPage from "@/app/buyer/page";
import SecurityLabPage from "@/app/security-lab/page";

describe("smoke: core pages render", () => {
  it("overview states the core principle", () => {
    render(<HomePage />);
    expect(
      screen.getByRole("heading", { name: /intent-to-execution integrity/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("The AI proposes")).toBeInTheDocument();
    expect(screen.getByText("RazorGuard authorizes")).toBeInTheDocument();
    expect(screen.getByText("The trusted executor executes")).toBeInTheDocument();
  });

  it("buyer page renders the four-step flow shell", () => {
    render(<BuyerPage />);
    expect(screen.getByTestId("step-authorization")).toBeInTheDocument();
    expect(screen.getByTestId("bypass-note")).toBeInTheDocument();
  });

  it("security lab is labeled as synthetic attack simulation", () => {
    render(<SecurityLabPage />);
    expect(
      screen.getByRole("heading", { name: /synthetic attack simulation/i }),
    ).toBeInTheDocument();
  });
});
