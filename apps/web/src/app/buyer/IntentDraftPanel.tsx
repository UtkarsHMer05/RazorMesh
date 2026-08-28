"use client";

/**
 * P3-M17: AI intent-draft review panel (trust-first).
 *
 * The draft is a PROPOSAL. This page renders the compiler's structured output
 * and the human's three honest options: confirm, reject, or answer later.
 * No secrets exist in this flow; the browser never receives any credential
 * (P3-S01) and never becomes an authority (P2 UI invariants).
 */

import { useCallback, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const _CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
function genUlid(): string {
  const now = Date.now();
  let value = BigInt(now) << BigInt(80);
  const randBytes = new Uint8Array(10);
  crypto.getRandomValues(randBytes);
  for (let i = 0; i < 10; i++) value |= BigInt(randBytes[i]) << BigInt((9 - i) * 8);
  let id = "";
  for (let shift = 125; shift >= 0; shift -= 5) {
    id += _CROCKFORD[Number((value >> BigInt(shift)) & BigInt(31))];
  }
  return id;
}

interface SemanticVerdict {
  action: "PASS" | "CHALLENGE" | "BLOCK";
  p_entailment: number;
  p_neutral: number;
  p_contradiction: number;
  model_id: string;
  policy_version: string;
  fail_closed: boolean;
}

interface DraftView {
  draft_id: string;
  state: string;
  payload: {
    product_summary?: string;
    hard?: Record<string, unknown>;
    semantic_constraints?: { text: string; family_hint?: string | null }[];
    ambiguities?: { question: string; options?: string[] }[];
    unspecified?: { field: string }[];
  };
  compiler_model: string;
  prompt_version: string;
  superseded_by: string | null;
  intent_id: string | null;
  confirmed_generation: number | null;
}

export function IntentDraftPanel({ onDraftConfirmed }: { onDraftConfirmed?: (draft: DraftView) => void }) {
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<DraftView | null>(null);
  const [semantic, setSemantic] = useState<SemanticVerdict | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const compile = useCallback(async () => {
    setBusy(true);
    setError(null);
    setSemantic(null); // fresh compile clears any prior verdict
    try {
      const res = await fetch(`${API}/buyer/intent-drafts/compile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          authorization_text: text,
          principal_id: `usr_${genUlid()}`,
          agent_id: `agt_${genUlid()}`,
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail?.code ?? "compile failed");
      setDraft(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [text]);

  const decide = useCallback(
    async (action: "confirm" | "reject") => {
      if (!draft) return;
      setBusy(true);
      setError(null);
      try {
        const res = await fetch(`${API}/buyer/intent-drafts/${draft.draft_id}/${action}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            action === "confirm"
              ? { confirmation_nonce: crypto.randomUUID(), actor: "human" }
              : { actor: "human" },
          ),
        });
        const body = await res.json();
        if (!res.ok) throw new Error(body.detail?.code ?? `${action} failed`);
        const updated = { ...draft, state: body.state ?? "CONFIRMED", ...body };
        setDraft(updated);
        if (action === "confirm" && onDraftConfirmed) {
          onDraftConfirmed(updated);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [draft],
  );

  return (
    <section className="card" data-testid="intent-draft-panel">
      <h2 className="card__title">AI authorization draft</h2>
      <p className="page-sub">
        Describe what you allow in your own words. The AI only drafts a
        structured proposal — nothing becomes authority until you confirm it.
        TEST MODE: no real money.
      </p>

      <label className="field-label" htmlFor="nl-auth">
        Your authorization
      </label>
      <textarea
        id="nl-auth"
        data-testid="nl-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        placeholder='e.g. "Buy wireless headphones under 5000 rupees, no subscription."'
      />
      <button
        data-testid="compile-btn"
        onClick={compile}
        disabled={busy || text.trim().length < 3}
      >
        Compile draft
      </button>

      {error && (
        <p role="alert" data-testid="draft-error" aria-live="polite">
          {error}
        </p>
      )}

      {draft && (
        <div data-testid="draft-view">
          <p data-testid="draft-state" aria-live="polite">
            State: <strong>{draft.state}</strong>
            {draft.confirmed_generation !== null && (
              <> · generation {draft.confirmed_generation}</>
            )}
          </p>

          <h3>Hard constraints</h3>
          <pre data-testid="draft-hard">{JSON.stringify(draft.payload.hard ?? {}, null, 2)}</pre>

          {(draft.payload.semantic_constraints?.length ?? 0) > 0 && (
            <>
              <h3>Semantic constraints</h3>
              <ul data-testid="draft-semantic">
                {draft.payload.semantic_constraints!.map((sc, i) => (
                  <li key={i}>{sc.text}</li>
                ))}
              </ul>
            </>
          )}

          {(draft.payload.ambiguities?.length ?? 0) > 0 ? (
            <>
              <h3>Ambiguities — please clarify by compiling again with details</h3>
              <ul data-testid="draft-ambiguities">
                {draft.payload.ambiguities!.map((a, i) => (
                  <li key={i}>{a.question}</li>
                ))}
              </ul>
            </>
          ) : null}

          {(draft.payload.unspecified?.length ?? 0) > 0 && (
            <>
              <h3>Unspecified by you</h3>
              <ul data-testid="draft-unspecified">
                {draft.payload.unspecified!.map((item, i) => (
                  <li key={i}>{item.field}</li>
                ))}
              </ul>
            </>
          )}

          {draft.superseded_by && (
            <p data-testid="superseded-note">Superseded by a newer draft.</p>
          )}

          {draft.state === "DRAFT" && (
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
              <button data-testid="confirm-draft" onClick={() => decide("confirm")} disabled={busy}>
                Confirm authorization
              </button>
              <button data-testid="reject-draft" onClick={() => decide("reject")} disabled={busy}>
                Reject
              </button>
            </div>
          )}

          {draft.state === "NEEDS_CLARIFICATION" && (
            <p data-testid="clarify-note">
              Resolve the ambiguities above by compiling a more specific request.
            </p>
          )}

          {draft.state === "REJECTED" && (
            <p data-testid="rejected-note">Draft rejected. Nothing was authorized.</p>
          )}

          {draft.state === "CONFIRMED" && (
            <p data-testid="confirmed-note">Authorization confirmed and bound to your account.</p>
          )}

          {semantic && (
            <div data-testid="semantic-verdict" className="card">
              <h4>Semantic verification <span className="tag">{semantic.model_id}</span></h4>
              <p data-testid="semantic-action">
                Semantic action: <strong>{semantic.action}</strong> (fail-closed:{" "}
                {String(semantic.fail_closed)})
              </p>
              <ul>
                <li>p_entailment {semantic.p_entailment.toFixed(3)}</li>
                <li>p_neutral {semantic.p_neutral.toFixed(3)}</li>
                <li>p_contradiction {semantic.p_contradiction.toFixed(3)}</li>
              </ul>
              <p className="page-sub">
                Thresholds {semantic.policy_version} — semantics only tighten
                deterministic RazorGuard decisions.
              </p>
            </div>
          )}

          <p className="page-sub">
            compiled by {draft.compiler_model} · prompt {draft.prompt_version}
          </p>
        </div>
      )}
    </section>
  );
}
