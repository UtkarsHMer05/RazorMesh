"use client";

/**
 * Phase-5 (M014/M016): global trace badge — compact live-trace indicator.
 *
 * Shows the backend-issued display trace (RM-XXXXXX), copy + open actions,
 * and deep-links every demo page via ?trace=. Short display id only; the
 * advanced technical ids live behind the disclosure.
 */

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getActiveTraceId, setActiveTraceId, subscribeTraceId } from "@/lib/live-trace";

const DEEP_LINK_ROUTES = ["/buyer", "/merchant", "/protocols", "/security-lab", "/audit"];

export function TraceBadge() {
  // SSR-safe: always start with the "no live mission" render so server HTML
  // matches the first client render; the real trace id arrives after mount
  // through the subscription (or the URL param effect below).
  const [registeredId, setRegisteredIdState] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [intentId, setIntentId] = useState<string | null>(null);
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    // Microtask boundary: adopt the already-active trace id without a
    // synchronous setState in the effect body (cascading-render guard).
    const id = getActiveTraceId();
    if (!id) return;
    const t = window.setTimeout(() => setRegisteredIdState(id), 0);
    return () => window.clearTimeout(t);
  }, []);
  useEffect(() => subscribeTraceId((id) => setRegisteredIdState(id)), []);
  const traceId = registeredId;

  // Deep-link adoption goes through the external registry (subscription
  // pattern): the effect only syncs the external system; the badge re-renders
  // from the subscription callback above.
  useEffect(() => {
    const urlParam = searchParams.get("trace");
    if (urlParam && /^RM-[0-9A-HJKMNP-TV-Z]{6}$/.test(urlParam)) {
      if (getActiveTraceId() !== urlParam) setActiveTraceId(urlParam);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!traceId || !showAdvanced) return;
    let cancelled = false;
    fetch(`/api/trace/${traceId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!cancelled && d?.trace) setIntentId(d.trace.intent_id);
      })
      .catch(() => setIntentId(null));
    return () => {
      cancelled = true;
    };
  }, [traceId, showAdvanced]);

  if (!traceId) {
    return (
      <div className="trace-badge trace-badge--empty" data-testid="trace-badge">
        <span className="trace-badge__dot" aria-hidden="true" />
        <span className="trace-badge__label">No live mission</span>
      </div>
    );
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(traceId);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const inDemoFlow = DEEP_LINK_ROUTES.includes(pathname ?? "");

  return (
    <div className="trace-badge" data-testid="trace-badge">
      <span className="trace-badge__dot trace-badge__dot--live" aria-hidden="true" />
      <span className="trace-badge__label">
        LIVE MISSION <strong className="trace-badge__id">{traceId}</strong>
      </span>
      <button
        type="button"
        className="trace-badge__btn"
        onClick={copy}
        aria-label={`Copy trace id ${traceId}`}
      >
        {copied ? "Copied" : "Copy"}
      </button>
      {inDemoFlow && (
        <button
          type="button"
          className="trace-badge__btn trace-badge__btn--ghost"
          onClick={() => setShowAdvanced((v) => !v)}
          aria-expanded={showAdvanced}
        >
          {showAdvanced ? "Hide links" : "Open trace in…"}
        </button>
      )}
      {showAdvanced && (
        <div className="trace-badge__menu" role="menu" aria-label="Open same trace on">
          {DEEP_LINK_ROUTES.filter((r) => r !== pathname).map((r) => (
            <Link key={r} href={`${r}?trace=${traceId}`} role="menuitem" className="trace-badge__link">
              {r === "/buyer"
                ? "Buyer"
                : r === "/merchant"
                  ? "Merchant"
                  : r === "/protocols"
                    ? "Protocols"
                    : r === "/security-lab"
                      ? "Security Lab"
                      : "Audit"}
            </Link>
          ))}
          <details className="trace-badge__advanced">
            <summary>Advanced · evidence ids</summary>
            <code>intent: {intentId ?? "—"}</code>
          </details>
        </div>
      )}
    </div>
  );
}
