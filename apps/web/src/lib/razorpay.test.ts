import { beforeEach, describe, expect, it, vi } from "vitest";
import { __resetRazorpayLoader, loadRazorpayCheckout, RAZORPAY_CHECKOUT_SRC } from "./razorpay";

describe("razorpay checkout loader", () => {
  beforeEach(() => {
    __resetRazorpayLoader();
    document.body.innerHTML = "";
    // fresh window state per test
    vi.stubGlobal("Razorpay", undefined);
    (window as unknown as { Razorpay?: unknown }).Razorpay = undefined;
  });

  it("injects exactly one script with the official src", async () => {
    const promise = loadRazorpayCheckout();
    const scripts = document.querySelectorAll(`#${"razorpay-checkout-v1"}`);
    expect(scripts.length).toBe(1);
    const el = scripts[0] as HTMLScriptElement;
    expect(el.src).toBe(RAZORPAY_CHECKOUT_SRC);

    // simulate successful load
    (window as unknown as { Razorpay?: unknown }).Razorpay = function FakeRz() {};
    el.onload?.(new Event("load"));
    await expect(promise).resolves.toBe(true);
    expect(document.querySelectorAll("script#razorpay-checkout-v1").length).toBe(1);
  });

  it("is idempotent while loading", async () => {
    const first = loadRazorpayCheckout();
    const second = loadRazorpayCheckout();
    expect(document.querySelectorAll("script#razorpay-checkout-v1").length).toBe(1);
    const el = document.querySelector("script#razorpay-checkout-v1") as HTMLScriptElement;
    (window as unknown as { Razorpay?: unknown }).Razorpay = function FakeRz() {};
    el.onload?.(new Event("load"));
    await expect(first).resolves.toBe(true);
    await expect(second).resolves.toBe(true);
  });

  it("reports failure and clears the tag for later retry", async () => {
    const promise = loadRazorpayCheckout();
    const el = document.querySelector("script#razorpay-checkout-v1") as HTMLScriptElement;
    el.onerror?.(new Event("error"));
    await expect(promise).resolves.toBe(false);
    expect(document.getElementById("razorpay-checkout-v1")).toBeNull();

    // retry path re-injects
    const retry = loadRazorpayCheckout();
    const retryEl = document.querySelector(
      "script#razorpay-checkout-v1",
    ) as HTMLScriptElement;
    expect(retryEl).not.toBeNull();
    (window as unknown as { Razorpay?: unknown }).Razorpay = function FakeRz() {};
    retryEl.onload?.(new Event("load"));
    await expect(retry).resolves.toBe(true);
  });
});
