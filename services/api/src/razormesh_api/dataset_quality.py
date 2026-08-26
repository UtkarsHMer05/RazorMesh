"""P3-M21: candidate validation — quality gates before any record joins the pool.

Validators are DETERMINISTIC and cheap (no model calls):

- schema validity            handled by AgentPayIRRecord itself;
- provenance completeness    qwen_provisional rows MUST carry a generator
                             request id and source case;
- degenerate-text checks     premise==hypothesis, near-empty bodies, missing
                             currency mentions where the family demands one;
- label-consistency signals  family-conditioned keyword evidence: e.g. a
                             trial_renewal_trap CONTRADICTION whose premise
                             never mentions any renewal/subscription term is
                             suspicious (recorded as a warning, not fatal —
                             humans make the final call at gold review).

Every check returns a structured reason so rejections are explainable and
auditable (P3-S20). Nothing here mutates authority state.
"""

from dataclasses import dataclass

from razormesh_api.agentpay_ir import AgentPayIRRecord

_RENEWAL_TERMS = (
    "renew",
    "subscription",
    "auto-renew",
    "recurring",
    "monthly",
    "trial",
    "membership",
)
_CURRENCY_TERMS = ("₹", "$", "€", "£", "inr", "usd", "eur", "gbp")


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    fatal: tuple[str, ...]
    warnings: tuple[str, ...]


def validate_candidate(record: AgentPayIRRecord) -> ValidationResult:
    fatal: list[str] = []
    warnings: list[str] = []

    # --- provenance --------------------------------------------------------
    if record.label_source == "qwen_provisional":
        if not record.provenance.generator_request_id:
            fatal.append("missing_generator_request_id")
        if not record.provenance.source_case_id:
            fatal.append("missing_source_case_id")

    # --- degenerate text ---------------------------------------------------
    p_norm = " ".join(record.premise.lower().split())
    h_norm = " ".join(record.hypothesis.lower().split())
    if p_norm == h_norm:
        fatal.append("premise_equals_hypothesis")
    if len(p_norm.split()) < 6:
        fatal.append("premise_too_short_for_evidence")
    if len(h_norm.split()) < 5:
        fatal.append("hypothesis_too_short_for_claim")

    # --- family-conditioned consistency signals ----------------------------
    blob = p_norm + " " + h_norm

    if record.family == "trial_renewal_trap" and record.label == "contradiction":
        if not any(term in p_norm for term in _RENEWAL_TERMS):
            warnings.append("contradiction-without-renewal-evidence-in-premise")

    if record.family == "currency_binding" and record.label != "neutral":
        if not any(term in blob for term in _CURRENCY_TERMS):
            warnings.append("no-currency-token-despite-currency-family")

    if record.family == "budget_ceiling" and record.label == "entailment":
        import re as _re

        if not _re.search(r"\d", record.premise):
            warnings.append("entailment-without-numeric-price")

    return ValidationResult(passed=not fatal, fatal=tuple(fatal), warnings=tuple(warnings))


# ---------------------------------------------------------------------------
# P3-M26 addendum: human gold-decision ingestion with INVALID exclusion.
# ---------------------------------------------------------------------------

GOLD_VALID_LABELS = frozenset({"entailment", "neutral", "contradiction"})


@dataclass(frozen=True)
class GoldIngestResult:
    """Human decisions split into usable gold labels vs excluded cards.

    - valid: record_id -> label (entailment/neutral/contradiction only);
    - excluded: record_id -> reason (label was 'invalid' or missing);
      excluded cards NEVER enter gold metrics (they are not force-labeled).
    """

    valid: dict[str, str]
    excluded: dict[str, str]


def ingest_gold_decisions(
    decisions: dict[str, dict[str, str]], known_record_ids: set[str] | None = None
) -> GoldIngestResult:
    valid: dict[str, str] = {}
    excluded: dict[str, str] = {}
    for record_id, entry in decisions.items():
        if known_record_ids is not None and record_id not in known_record_ids:
            excluded[record_id] = "unknown_record_id"
            continue
        label = str(entry.get("label", "")).lower() if isinstance(entry, dict) else ""
        if label in GOLD_VALID_LABELS:
            valid[record_id] = label
        elif label == "invalid":
            reason = str(entry.get("reason") or "").strip()
            excluded[record_id] = reason or "malformed_or_semantically_nonsensical"
        else:
            excluded[record_id] = "unlabeled_or_unknown_label"
    return GoldIngestResult(valid=valid, excluded=excluded)
