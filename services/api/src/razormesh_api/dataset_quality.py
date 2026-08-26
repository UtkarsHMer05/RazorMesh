"""P3-M21: deterministic candidate quality gates and batch rejection report.

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

import json
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import ValidationError

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
_SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|tr)_[A-Za-z0-9_-]{16,}\b", re.IGNORECASE),
    re.compile(r"\brzp_(?:live|test)_[A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bbearer\s+[A-Za-z0-9._-]{16,}", re.IGNORECASE),
)
_GENERATION_ARTIFACTS = (
    ("generation_artifact_thinking_tag", re.compile(r"</?think>", re.IGNORECASE)),
    ("generation_artifact_markdown_fence", re.compile(r"```")),
    (
        "generation_artifact_json_echo",
        re.compile(r"[\{\[]\s*[\"']?(?:premise|hypothesis)[\"']?\s*:", re.IGNORECASE),
    ),
    (
        "generation_artifact_instruction_echo",
        re.compile(r"\b(?:output only json|reference style|label to preserve)\b", re.IGNORECASE),
    ),
    (
        "generation_artifact_model_disclaimer",
        re.compile(r"\bas an ai(?: language model)?\b", re.IGNORECASE),
    ),
)
_UNTRUSTED_AUTHORITY = re.compile(
    r"\b(?:the\s+)?(?:ai|agent|model|merchant|seller|system|product page|checkout)\s+"
    r"(?:(?:has|is|claims?|says?|states?)\s+)?(?:authorized|approved|confirmed)\b",
    re.IGNORECASE,
)
_BYPASS_CLAIM = re.compile(
    r"\b(?:bypass|skip|without)\b.{0,36}\b(?:human |buyer )?"
    r"(?:authorization|confirmation|razorguard|payment check)\b",
    re.IGNORECASE,
)
_MALFORMED_MONEY = (
    re.compile(r"\d+\.\d{3,}\b"),
    re.compile(r"\d{1,3},\d{1,2}(?![\d,])"),
    re.compile(r"(?:₹|\$|€|£)\s*(?:₹|\$|€|£)"),
    re.compile(r"\b(?:INR|USD|EUR|GBP)\s+(?:INR|USD|EUR|GBP)\b", re.IGNORECASE),
)
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    fatal: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CandidateRejection:
    line_number: int
    record_id: str | None
    reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidatePoolResult:
    input_rows: int
    accepted: tuple[AgentPayIRRecord, ...]
    rejected: tuple[CandidateRejection, ...]
    warnings_by_record: dict[str, tuple[str, ...]]
    reason_counts: dict[str, int]
    warning_counts: dict[str, int]


def validate_candidate(record: AgentPayIRRecord) -> ValidationResult:
    fatal: list[str] = []
    warnings: list[str] = []

    # --- provenance --------------------------------------------------------
    if record.label_source == "qwen_provisional":
        if "qwen" not in record.provenance.generator.lower():
            fatal.append("unexpected_provisional_generator")
        if not record.provenance.generator_model:
            fatal.append("missing_generator_model")
        if not record.provenance.prompt_version:
            fatal.append("missing_prompt_version")
        if not record.provenance.batch_id:
            fatal.append("missing_batch_id")
        if not record.provenance.generator_request_id:
            fatal.append("missing_generator_request_id")
        if not record.provenance.source_case_id:
            fatal.append("missing_source_case_id")

    # --- degenerate text ---------------------------------------------------
    p_norm = " ".join(record.premise.lower().split())
    h_norm = " ".join(record.hypothesis.lower().split())
    blob = p_norm + " " + h_norm
    if p_norm == h_norm:
        fatal.append("premise_equals_hypothesis")
    if len(p_norm.split()) < 6:
        fatal.append("premise_too_short_for_evidence")
    if len(h_norm.split()) < 5:
        fatal.append("hypothesis_too_short_for_claim")
    if _CONTROL_CHARACTERS.search(record.premise + record.hypothesis):
        fatal.append("control_character_in_text")

    # --- secret leakage and generation artifacts --------------------------
    serialized = record.model_dump_json()
    if any(pattern.search(serialized) for pattern in _SECRET_PATTERNS):
        fatal.append("secret_like_value")
    for code, pattern in _GENERATION_ARTIFACTS:
        if pattern.search(record.premise) or pattern.search(record.hypothesis):
            fatal.append(code)

    # --- malformed money and false payment-authority claims ---------------
    if any(pattern.search(blob) for pattern in _MALFORMED_MONEY):
        fatal.append("malformed_money_expression")
    if _UNTRUSTED_AUTHORITY.search(record.hypothesis) or _BYPASS_CLAIM.search(record.hypothesis):
        fatal.append("hypothesis_payment_authority_misinformation")
    if _UNTRUSTED_AUTHORITY.search(record.premise) or _BYPASS_CLAIM.search(record.premise):
        warnings.append("premise_contains_untrusted_authority_claim")

    # --- family-conditioned consistency signals ----------------------------
    if record.family == "trial_renewal_trap" and record.label == "contradiction":
        if not any(term in p_norm for term in _RENEWAL_TERMS):
            fatal.append("contradiction-without-renewal-evidence-in-premise")

    if record.family == "currency_binding" and record.label != "neutral":
        if not any(term in blob for term in _CURRENCY_TERMS):
            fatal.append("no-currency-token-despite-currency-family")

    if record.family == "budget_ceiling" and record.label == "entailment":
        if not re.search(r"\d", record.premise):
            fatal.append("entailment-without-numeric-price")

    if record.family == "injection_resistance" and not re.search(
        r"\b(?:system|instruction|ignore|bypass|approv\w*|authoriz\w*|prompt|assistant[_-]?action)\b",
        p_norm,
    ):
        fatal.append("injection-family-without-injection-signal")

    if record.family == "safe_lookalike" and not re.search(
        r"\b(?:compatible|counterfeit|lookalike|similar|third-party|genuine|exact|model)\b",
        p_norm,
    ):
        fatal.append("lookalike-family-without-identity-signal")

    return ValidationResult(
        passed=not fatal,
        fatal=tuple(dict.fromkeys(fatal)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def validate_candidate_jsonl(lines: Iterable[str]) -> CandidatePoolResult:
    """Parse and validate a complete candidate JSONL pool.

    Duplicate record ids and duplicate canonical content reject every involved
    row so downstream selection never depends on input ordering.
    """
    input_rows = 0
    parsed: list[tuple[int, AgentPayIRRecord, ValidationResult]] = []
    rejected: list[CandidateRejection] = []

    for line_number, line in enumerate(lines, start=1):
        input_rows += 1
        if not line.strip():
            rejected.append(CandidateRejection(line_number, None, ("blank_line",)))
            continue
        raw: object
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            rejected.append(CandidateRejection(line_number, None, ("invalid_json",)))
            continue
        record_id = raw.get("record_id") if isinstance(raw, dict) else None
        try:
            record = AgentPayIRRecord.model_validate(raw)
        except ValidationError:
            rejected.append(
                CandidateRejection(
                    line_number,
                    str(record_id) if record_id is not None else None,
                    ("schema_invalid",),
                )
            )
            continue
        parsed.append((line_number, record, validate_candidate(record)))

    id_counts = Counter(record.record_id for _, record, _ in parsed)
    content_counts = Counter(record.content_sha256 for _, record, _ in parsed)
    accepted: list[AgentPayIRRecord] = []
    warnings_by_record: dict[str, tuple[str, ...]] = {}
    for line_number, record, validation in parsed:
        reasons = list(validation.fatal)
        if id_counts[record.record_id] > 1:
            reasons.append("duplicated_record_id")
        if content_counts[record.content_sha256] > 1:
            reasons.append("duplicated_content")
        if validation.warnings:
            warnings_by_record[record.record_id] = validation.warnings
        if reasons:
            rejected.append(
                CandidateRejection(
                    line_number,
                    record.record_id,
                    tuple(dict.fromkeys(reasons)),
                    validation.warnings,
                )
            )
        else:
            accepted.append(record)

    rejected.sort(key=lambda item: item.line_number)
    reason_counts = Counter(reason for item in rejected for reason in item.reasons)
    warning_counts = Counter(
        warning for warnings in warnings_by_record.values() for warning in warnings
    )
    return CandidatePoolResult(
        input_rows=input_rows,
        accepted=tuple(accepted),
        rejected=tuple(rejected),
        warnings_by_record=warnings_by_record,
        reason_counts=dict(sorted(reason_counts.items())),
        warning_counts=dict(sorted(warning_counts.items())),
    )


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
