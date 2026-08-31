/**
 * Phase-5 (M012/M013): shared live-trace frontend store + bounded polling.
 *
 * Backend is the source of truth. This module only caches what the trace API
 * returns. "Live updates" use robust bounded polling (reconnect-safe by
 * design: each poll re-derives from server state; a failed poll retries on
 * the next tick) — chosen over SSE because the trace lifecycle is short and
 * the API is request/response oriented; no overengineering per master prompt.
 */

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type TraceStageEvent = {
  seq: number;
  ts: string;
  stage: string;
  kind: string;
  title: string;
  status: string;
  detail: string | null;
  source: string;
  ids: Record<string, string>;
  evidence: Record<string, unknown>;
};

export type TraceSummary = {
  trace_id: string;
  intent_id: string;
  draft_id: string | null;
  checkout_id: string | null;
  run_id: string | null;
  created_at: string;
  updated_at: string;
  state: string;
  final_decision: string | null;
  ticket_state: string | null;
  provider_contacted: boolean;
  provider_call_count: number;
  amount_minor: number | null;
  currency: string | null;
};

export type TraceData = { trace: TraceSummary; events: TraceStageEvent[] };

const POLL_MS_DEFAULT = 1500;
const POLL_MS_MAX = 5000;
const DISPLAY_TRACE_RE = /^RM-[0-9A-HJKMNP-TV-Z]{6}$/;
export const INTENT_RE = /^intent_[0-9A-HJKMNP-TV-Z]{26}$/;

export function isDisplayTraceId(value: string): boolean {
  return DISPLAY_TRACE_RE.test(value);
}

/**
 * Global in-memory registry of the "active" trace id. Survives client-side
 * navigation (Next App Router keeps the JS context within a session) and is
 * re-hydrated from localStorage on load, so the trace survives reload too.
 * Deep links (?trace=RM-...) take precedence when present.
 */
const TRACE_KEY = "razormesh.phase5.trace";
const subscribers = new Set<(id: string | null) => void>();
let activeTraceId: string | null = null;

function readStored(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const v = window.localStorage.getItem(TRACE_KEY);
    return v && isDisplayTraceId(v) ? v : null;
  } catch {
    return null;
  }
}

export function getActiveTraceId(): string | null {
  if (activeTraceId === null) activeTraceId = readStored();
  return activeTraceId;
}

export function setActiveTraceId(id: string | null): void {
  if (id !== null && !isDisplayTraceId(id)) return;
  activeTraceId = id;
  if (typeof window !== "undefined") {
    try {
      if (id) window.localStorage.setItem(TRACE_KEY, id);
      else window.localStorage.removeItem(TRACE_KEY);
    } catch {
      /* storage unavailable — in-memory only */
    }
  }
  subscribers.forEach((fn) => fn(id));
}

export function subscribeTraceId(fn: (id: string | null) => void): () => void {
  subscribers.add(fn);
  return () => subscribers.delete(fn);
}

/** Fetch a trace by display id from the backend (single source of truth). */
export async function fetchTrace(traceId: string): Promise<TraceData | null> {
  if (!isDisplayTraceId(traceId)) return null;
  const res = await fetch(`/api/trace/${traceId}`, { cache: "no-store" });
  if (!res.ok) return null;
  return (await res.json()) as TraceData;
}

/** Resolve (or lazily mint) the trace for an intent the backend created. */
export async function resolveTraceForIntent(intentId: string): Promise<TraceSummary | null> {
  if (!INTENT_RE.test(intentId)) return null;
  const res = await fetch(`/api/trace/by-intent/${intentId}`, { cache: "no-store" });
  if (!res.ok) return null;
  return (await res.json()) as TraceSummary;
}

/**
 * useLiveTrace — the shared store hook (M013).
 *
 * - binds to the global active trace id (cross-page continuity);
 * - deep link (?trace=) overrides on mount;
 * - polls `/api/trace/events` incrementally while `active` (bounded backoff,
 *   stops after `idleAfter` consecutive no-change polls when `autoStop`);
 * - reload/reconnect recovers from server state by construction.
 */
export function useLiveTrace(options?: {
  active?: boolean;
  pollMs?: number;
  autoStop?: boolean;
  idleAfter?: number;
}) {
  const { active = true, pollMs = POLL_MS_DEFAULT, autoStop = true, idleAfter = 12 } =
    options ?? {};
  const [summary, setSummary] = useState<TraceSummary | null>(null);
  const [events, setEvents] = useState<TraceStageEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const lastSeqRef = useRef(0);
  const idleRef = useRef(0);

  const setTraceId = useCallback((id: string | null) => {
    setActiveTraceId(id);
    setSummary(null);
    setEvents([]);
    lastSeqRef.current = 0;
    idleRef.current = 0;
  }, []);

  // Deep-link support (M016): ?trace=RM-XXXXXX wins over the stored trace.
  // Adopted inside the store's subscription callback (external-system sync),
  // not as a direct setState in the effect body.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const param = new URLSearchParams(window.location.search).get("trace");
    if (param && isDisplayTraceId(param) && param !== getActiveTraceId()) {
      setActiveTraceId(param);
    }
  }, []);

  // Sync hook state with the external trace-id registry (subscription pattern).
  const [registeredId, setRegisteredId] = useState<string | null>(() => getActiveTraceId());
  useEffect(() => subscribeTraceId((id) => setRegisteredId(id)), []);
  const traceId = registeredId;

  useEffect(() => {
    if (!traceId) return; // nothing to clear: summary/events already null for a null trace
    let cancelled = false;
    const load = async () => {
      setError(null);
      try {
        const data = await fetchTrace(traceId);
        if (cancelled || !data) return;
        setSummary(data.trace);
        setEvents(data.events);
        lastSeqRef.current = data.events.reduce((m, e) => Math.max(m, e.seq), 0);
      } catch {
        if (!cancelled) setError("Trace unavailable");
      }
    };
    const transition = window.setTimeout(load, 0); // async boundary: no sync setState in effect
    return () => {
      cancelled = true;
      window.clearTimeout(transition);
    };
  }, [traceId]);

  // When the active trace becomes null or changes, clear cached view state
  // via a microtask (no synchronous setState inside the effect body).
  useEffect(() => {
    if (traceId === null && (summary !== null || events.length > 0)) {
      const t = window.setTimeout(() => {
        setSummary(null);
        setEvents([]);
        lastSeqRef.current = 0;
      }, 0);
      return () => window.clearTimeout(t);
    }
  }, [traceId, summary, events.length]);

  // Bounded polling while active (M012).
  useEffect(() => {
    if (!active || !traceId) return;
    let cancelled = false;
    let delay = pollMs;
    const tick = async () => {
      if (cancelled) return;
      try {
        const res = await fetch(`/api/trace/${traceId}/events?after_seq=${lastSeqRef.current}`, {
          cache: "no-store",
        });
        if (res.ok) {
          const body = (await res.json()) as {
            count: number;
            events: TraceStageEvent[];
          };
          if (!cancelled && body.count > 0) {
            setEvents((prev) => [...prev, ...body.events]);
            lastSeqRef.current = body.events.reduce(
              (m, e) => Math.max(m, e.seq),
              lastSeqRef.current,
            );
            idleRef.current = 0;
          } else if (!cancelled) {
            idleRef.current += 1;
          }
          delay = pollMs; // healthy → base rate
        } else {
          delay = Math.min(delay * 1.5, POLL_MS_MAX);
        }
      } catch {
        delay = Math.min(delay * 1.5, POLL_MS_MAX);
      }
      if (autoStop && idleRef.current >= idleAfter) return; // bounded: stop when quiet
      timer = window.setTimeout(tick, delay);
    };
    let timer = window.setTimeout(tick, delay);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [active, traceId, pollMs, autoStop, idleAfter]);

  return useMemo(
    () => ({ traceId, summary, events, error, setTraceId }),
    [traceId, summary, events, error, setTraceId],
  );
}
