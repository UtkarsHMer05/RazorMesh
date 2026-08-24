/**
 * P2-M20: official Razorpay Standard Checkout script loader.
 *
 * Loads https://checkout.razorpay.com/v1/checkout.js exactly once per page,
 * idempotently, with typed load/error states. No secret material is involved:
 * the script itself is public; the Key ID is supplied later via the backend
 * launch payload (P2-S03/S04).
 */

export const RAZORPAY_CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";
const SCRIPT_ID = "razorpay-checkout-v1";

let inflight: Promise<boolean> | null = null;

declare global {
  interface Window {
    Razorpay?: unknown;
  }
}

function inject(): Promise<boolean> {
  return new Promise((resolve) => {
    const existing = document.getElementById(SCRIPT_ID);
    if (existing && window.Razorpay) {
      resolve(true);
      return;
    }
    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.src = RAZORPAY_CHECKOUT_SRC;
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => {
      // allow a retry on a later user action
      document.getElementById(SCRIPT_ID)?.remove();
      inflight = null;
      resolve(false);
    };
    document.body.appendChild(script);
  });
}

/** Resolves true when window.Razorpay is available; false on load failure. */
export function loadRazorpayCheckout(): Promise<boolean> {
  if (typeof window === "undefined") return Promise.resolve(false);
  if (window.Razorpay) return Promise.resolve(true);
  if (!inflight) inflight = inject();
  return inflight;
}

/** Test seam. */
export function __resetRazorpayLoader(): void {
  inflight = null;
}
