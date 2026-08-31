import { describe, expect, it } from "vitest";

import { formatTransactionValue } from "./formatTransactionValue";

describe("F003 formatTransactionValue — type-aware diff rendering", () => {
  it("money fields render as ₹ with two decimals", () => {
    expect(formatTransactionValue("unit_price_minor", 129900)).toBe("₹1,299.00");
    expect(formatTransactionValue("total_minor", 479900)).toBe("₹4,799.00");
    expect(formatTransactionValue("shipping_minor", 0)).toBe("₹0.00");
    expect(formatTransactionValue("tax_minor", 12345)).toBe("₹123.45");
    expect(formatTransactionValue("recurring_amount_minor", 49900)).toBe("₹499.00");
    expect(formatTransactionValue("fee_minor", 19900)).toBe("₹199.00");
  });

  it("quantity renders as an integer", () => {
    expect(formatTransactionValue("quantity", 2)).toBe("2");
    expect(formatTransactionValue("quantity", 0)).toBe("0");
  });

  it("currency renders uppercased", () => {
    expect(formatTransactionValue("currency", "inr")).toBe("INR");
    expect(formatTransactionValue("currency", "USD")).toBe("USD");
  });

  it("merchant renders as readable id/name", () => {
    expect(formatTransactionValue("merchant_id", "mrc_gadgethub")).toBe("Mrc Gadgethub");
    expect(formatTransactionValue("merchant", { name: "mrc_gadgethub" })).toBe("Mrc Gadgethub");
  });

  it("condition maps to readable labels", () => {
    expect(formatTransactionValue("condition", "new")).toBe("New");
    expect(formatTransactionValue("condition", "used")).toBe("Used");
    expect(formatTransactionValue("condition", "refurbished")).toBe("Refurbished");
    expect(formatTransactionValue("condition", "open-box")).toBe("open-box");
  });

  it("recurring renders string and object forms concisely", () => {
    expect(formatTransactionValue("recurring", "monthly")).toBe("monthly");
    expect(formatTransactionValue("recurring", "none")).toBe("none");
    expect(formatTransactionValue("recurring", true)).toBe("Yes");
    expect(formatTransactionValue("recurring", false)).toBe("No");
    expect(formatTransactionValue("recurring", { interval: "monthly", amount_minor: 49900 })).toBe(
      "monthly, ₹499.00",
    );
    expect(formatTransactionValue("recurring_terms", ["monthly"])).toBe("monthly");
  });

  it("null/undefined/empty render as None or Not specified", () => {
    expect(formatTransactionValue("total_minor", null)).toBe("None");
    expect(formatTransactionValue("merchant_id", undefined)).toBe("None");
    expect(formatTransactionValue("condition", null)).toBe("Not specified");
    expect(formatTransactionValue("note", "")).toBe("None");
  });

  it("booleans render as Yes/No", () => {
    expect(formatTransactionValue("shipping_included", true)).toBe("Yes");
    expect(formatTransactionValue("insurance_added", false)).toBe("No");
  });

  it("structured objects render concisely — never [object Object]", () => {
    const out = formatTransactionValue("line_item", { sku: "ABC", quantity: 2 });
    expect(out).not.toMatch(/\[object Object\]/);
    expect(out).toContain("sku=ABC");
    expect(out).toContain("quantity=2");
    expect(formatTransactionValue("line_item", {})).toBe("{empty}");
  });

  it("total function: garbage input never produces NaN/undefined/[object Object]", () => {
    const banned = /NaN|\[object Object\]|undefined/;
    const garbage: [string, unknown][] = [
      ["total_minor", NaN],
      ["total_minor", {}],
      ["total_minor", []],
      ["quantity", undefined],
      ["recurring", NaN],
      ["anything", Symbol("x")],
      ["nested", { deep: { deeper: NaN } }],
    ];
    for (const [field, value] of garbage) {
      const out = formatTransactionValue(field, value);
      expect(out, `${field}=${String(value)}`).toMatch(/.+/);
      expect(banned.test(out), `${field} -> ${out}`).toBe(false);
    }
  });
});
