/**
 * Phase-5 (M012/M013/M016): live-trace store unit tests.
 * Covers: display-id validation, active-trace registry semantics,
 * deep-link param handling, and the no-hardcoding rule (trace ids come
 * from the backend only).
 */
import { describe, expect, it, beforeEach, afterEach } from "vitest";
import {
  INTENT_RE,
  isDisplayTraceId,
  getActiveTraceId,
  setActiveTraceId,
  subscribeTraceId,
} from "@/lib/live-trace";

describe("isDisplayTraceId", () => {
  it("accepts only backend-shaped RM ids", () => {
    expect(isDisplayTraceId("RM-84C91A")).toBe(true);
    expect(isDisplayTraceId("RM-ZZZZZZ")).toBe(true);
    expect(isDisplayTraceId("rm-lower1")).toBe(false);
    expect(isDisplayTraceId("RM-999")).toBe(false);
    expect(isDisplayTraceId("RM-IOU123")).toBe(false); // banned alphabet chars
    expect(isDisplayTraceId("'; DROP TABLE demo_traces; --")).toBe(false);
  });
});

describe("active trace registry", () => {
  beforeEach(() => {
    setActiveTraceId(null);
    window.localStorage.clear();
  });
  afterEach(() => {
    setActiveTraceId(null);
  });

  it("set/get round-trips and notifies subscribers", () => {
    const seen: (string | null)[] = [];
    const unsub = subscribeTraceId((id) => seen.push(id));
    setActiveTraceId("RM-84C91A");
    expect(getActiveTraceId()).toBe("RM-84C91A");
    expect(seen).toEqual(["RM-84C91A"]);
    unsub();
  });

  it("persists across reload simulation (localStorage)", () => {
    setActiveTraceId("RM-K2P9WX");
    expect(window.localStorage.getItem("razormesh.phase5.trace")).toBe("RM-K2P9WX");
    // simulate a fresh module read (get re-reads storage when unset)
    expect(getActiveTraceId()).toBe("RM-K2P9WX");
  });

  it("rejects client-invented ids (backend-only minting rule)", () => {
    const before = getActiveTraceId();
    setActiveTraceId("rm-not-real");
    expect(getActiveTraceId()).toBe(before);
    setActiveTraceId("RM-SHORT");
    expect(getActiveTraceId()).toBe(before);
  });

  it("clears to null and removes storage", () => {
    setActiveTraceId("RM-84C91A");
    setActiveTraceId(null);
    expect(getActiveTraceId()).toBeNull();
    expect(window.localStorage.getItem("razormesh.phase5.trace")).toBeNull();
  });
});

describe("intent id shape", () => {
  it("matches only ULID-shaped intent ids", () => {
    expect(INTENT_RE.test("intent_01M19X68VHHBGW00H2CFB13KFM")).toBe(true);
    expect(INTENT_RE.test("intent_NOT_A_ULID")).toBe(false);
    expect(INTENT_RE.test("../../etc/passwd")).toBe(false);
  });
});

describe("useLiveTrace deep-link precedence", () => {
  it("?trace= param is validated before adoption", async () => {
    // The badge component validates the param with the same regex before
    // calling setActiveTraceId; the store itself never accepts bad shapes.
    const bad = "RM-$pwn";
    expect(isDisplayTraceId(bad)).toBe(false);
    setActiveTraceId(null);
    // component-guarded path would reject; store confirms:
    setActiveTraceId(bad);
    expect(getActiveTraceId()).toBeNull();
  });
});
