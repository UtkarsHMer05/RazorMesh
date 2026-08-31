/**
 * F003: one reusable type-aware formatter for authorization-vs-current diffs.
 *
 * Money fields render as ₹; everything else renders by its own type so no
 * field ever shows ₹NaN, NaN or [object Object]. Total function: any input
 * yields a judge-readable string.
 */

const MONEY_FIELDS = new Set([
  "unit_price_minor",
  "shipping_minor",
  "fee_minor",
  "fees_minor",
  "tax_minor",
  "total_minor",
  "computed_total_minor",
  "recurring_amount_minor",
  "amount_minor",
  "authorized_minor",
  "reserved_minor",
  "committed_minor",
  "available_minor",
]);

const CONDITION_LABELS: Record<string, string> = {
  new: "New",
  used: "Used",
  refurbished: "Refurbished",
};

const RECURRING_LABELS: Record<string, string> = {
  none: "none",
  monthly: "monthly",
  quarterly: "quarterly",
  semiannual: "semi-annual",
  annual: "annual",
};

/** Money in integer minor units → "₹1,234.50" (integer-safe). */
export const formatMinor = (minor: number): string =>
  `₹${(minor / 100).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const isMoneyField = (field: string): boolean =>
  MONEY_FIELDS.has(field) || field.endsWith("_minor");

const formatRecurringObject = (value: Record<string, unknown>): string => {
  const parts: string[] = [];
  const interval = value.interval ?? value.cycle ?? value.period;
  if (typeof interval === "string") {
    parts.push(RECURRING_LABELS[interval.toLowerCase()] ?? interval.toLowerCase());
  } else if (typeof value.frequency === "string") {
    parts.push(value.frequency.toLowerCase());
  }
  const amount = value.amount_minor ?? value.recurring_amount_minor;
  if (typeof amount === "number" && Number.isFinite(amount)) {
    parts.push(formatMinor(amount));
  }
  if (parts.length === 0) return conciseObject(value);
  return parts.join(", ");
};

/** k=v rendering for structured objects — never [object Object]. */
export const conciseObject = (value: Record<string, unknown>): string => {
  const entries = Object.entries(value)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${k}=${formatTransactionValue(k, v)}`);
  const text = entries.length > 0 ? entries.join(" · ") : "empty";
  return `{${text}}`;
};

/**
 * Format one transaction diff value. Total: never throws, never emits
 * "NaN", "undefined" or "[object Object]".
 */
export const formatTransactionValue = (field: string, value: unknown): string => {
  const key = field.toLowerCase();

  if (value === null || value === undefined) {
    return key === "condition" ? "Not specified" : "None";
  }

  if (isMoneyField(key)) {
    if (typeof value === "number" && Number.isFinite(value)) return formatMinor(value);
    if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) {
      return formatMinor(Number(value));
    }
    return "None";
  }

  if (key === "quantity" || key === "qty") {
    if (typeof value === "number" && Number.isFinite(value)) return String(Math.trunc(value));
    if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) {
      return String(Math.trunc(Number(value)));
    }
    return "None";
  }

  if (key === "currency") {
    return typeof value === "string" && value !== "" ? value.toUpperCase() : "None";
  }

  if (key === "merchant" || key === "merchant_id" || key === "seller" || key === "seller_name") {
    if (typeof value === "string" && value !== "") {
      return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    }
    if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      const obj = value as Record<string, unknown>;
      const name = obj.name ?? obj.merchant_name ?? obj.title;
      if (typeof name === "string" && name !== "") {
        return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
      }
      return conciseObject(obj);
    }
    return "None";
  }

  if (key === "condition") {
    if (typeof value === "string" && value !== "") {
      return CONDITION_LABELS[value.toLowerCase()] ?? value;
    }
    return "Not specified";
  }

  if (key === "recurring" || key === "recurring_terms" || key === "renewal") {
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (typeof value === "string") return RECURRING_LABELS[value.toLowerCase()] ?? value.toLowerCase();
    if (Array.isArray(value)) {
      const inner = value.filter((v) => v !== null && v !== undefined);
      return inner.length === 0 ? "none" : inner.map((v) => formatTransactionValue(key, v)).join(", ");
    }
    if (typeof value === "object") return formatRecurringObject(value as Record<string, unknown>);
    return "Not specified";
  }

  if (typeof value === "boolean") return value ? "Yes" : "No";

  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : "None";
  }

  if (typeof value === "string") return value === "" ? "None" : value;

  if (Array.isArray(value)) {
    const inner = value.filter((v) => v !== null && v !== undefined);
    return inner.length === 0 ? "None" : inner.map((v) => formatTransactionValue(field, v)).join(", ");
  }

  if (typeof value === "object") {
    return conciseObject(value as Record<string, unknown>);
  }

  return String(value);
};

export default formatTransactionValue;
