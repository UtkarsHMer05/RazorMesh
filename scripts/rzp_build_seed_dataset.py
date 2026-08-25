#!/usr/bin/env python3
"""P3-M19: build the DETERMINISTIC seed dataset (AgentPay-IR v0.1).

For each compiler-golden case this emits up to three NLI records derived by
FIXED templates — premise = synthesized commerce evidence, hypothesis = the
confirmed-authorization statement, label chosen BY CONSTRUCTION:

- ENTAILMENT      evidence matches the human's stated constraints;
- CONTRADICTION   evidence violates one stated hard/semantic constraint;
- NEUTRAL         evidence is silent on a dimension the draft left unspecified
                  or ambiguous (insufficient information, never a guess).

record_id is DERIVED deterministically from content so identical inputs always
yield identical ids across runs. No Qwen involvement (label_source stays
"template_truth"; M20 adds provisional paraphrases separately).
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from razormesh_api.agentpay_ir import (
    AgentPayIRRecord,
    Provenance,
    make_record,
)

GOLDEN = REPO_ROOT / "data" / "phase3" / "compiler_golden" / "golden_set.jsonl"
OUT_DIR = REPO_ROOT / "data" / "phase3" / "dataset" / "seed"

_CREATED = datetime(2026, 8, 26, 0, 0, 0, tzinfo=UTC)  # fixed: determinism


def _det_record_id(premise: str, hypothesis: str, label: str, salt: str) -> str:
    digest = hashlib.sha256(f"{premise}|{hypothesis}|{label}|{salt}".encode()).digest()
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "air_" + "".join(alphabet[b % 32] for b in digest[:26])


def _money_words(minor: int | None, currency: str | None) -> str:
    if minor is None or currency is None:
        return "an unstated budget"
    major = minor / 100
    symbols = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}
    sym = symbols.get(currency, f"{currency} ")
    return f"{sym}{major:,.2f}"


def _evidence_for(case: dict, variant: str) -> tuple[str, str, str]:
    """Return (premise, hypothesis, label) for the requested variant."""
    exp = case["expected"]
    product = _product_of(case)
    session_ctx = f'Session context — human request: "{case["input_text"][:140]}". ' 
    amount = exp.get("max_amount_minor")
    currency = exp.get("currency")
    money = _money_words(amount, None if currency == "UNSPECIFIED" else currency)

    if variant == "entailment":
        premise = (
            f"{session_ctx}Product page states: {product}, priced at {money}, "
            "in stock, sold with standard marketplace terms."
        )
        hypothesis = f"The human authorized purchasing {product} within {money}."
        return premise, hypothesis, "entailment"

    if variant == "contradiction":
        # Violate whichever constraint the human actually stated hardest.
        brands = exp.get("brands") or ()
        if brands:
            other = "a non-matching competitor brand"
            premise = f"Product page states: {other} {product}, priced at {money}."
            hypothesis = (
                f"The human authorized only {'/'.join(brands)} brand for this purchase."
            )
        elif exp.get("recurring_forbidden"):
            premise = (
                f"{session_ctx}Checkout page states: {product} enrolls the "
                "buyer into a monthly auto-renewing plan after a 7-day trial."
            )
            hypothesis = "The human forbade any recurring charges for this purchase."
        elif exp.get("quantity_max") not in (None, 1):
            premise = (
                f"{session_ctx}Cart preview states: minimum order quantity "
                f"5 units of {product}."
            )
            hypothesis = (
                f"The human limited this purchase to at most "
                f"{exp['quantity_max']} unit(s)."
            )
        else:
            premise = (
                f"{session_ctx}Product page states: {product}, on flash sale "
                f"at {_money_words((amount or 100000) * 4, currency)}."
            )
            hypothesis = f"The human set a hard ceiling of {money} for this purchase."
        return premise, hypothesis, "contradiction"

    # neutral: evidence silent on an unspecified/ambiguous dimension
    silent_topic = "the seller's identity and return window"
    premise = (
        f"{session_ctx}Listing provides only a photo of {product}; no text "
        f"about {silent_topic}, no price breakdown beyond 'contact seller'."
    )
    hypothesis = f"The human authorized this specific {product} purchase."
    return premise, hypothesis, "neutral"


def _product_of(case: dict) -> str:
    text = case["input_text"].lower()
    for noun in (
        "wireless earbuds",
        "mechanical keyboard",
        "usb-c cable",
        "phone",
        "coffee grinder",
        "fitness band",
        "noise-cancelling headphones",
        "air fryer",
        "router",
        "desk lamp",
        "blender",
        "webcam",
        "headphones",
        "camera",
        "laptop",
        "monitor",
        "speaker",
    ):
        if noun in text:
            return noun
    words = [w for w in text.replace(".", "").split() if len(w) > 3]
    return words[-1] if words else "item"


def main() -> int:
    cases = [
        json.loads(line) for line in GOLDEN.read_text().splitlines() if line.strip()
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    records: list[AgentPayIRRecord] = []
    for case in cases:
        cid = case["case_id"]
        family = _family_for(case["category"])
        difficulty = case["difficulty"]
        for variant in ("entailment", "contradiction", "neutral"):
            premise, hypothesis, label = _evidence_for(case, variant)
            rid = _det_record_id(premise, hypothesis, label, salt=cid + variant)
            records.append(
                make_record(
                    record_id=rid,
                    premise=premise,
                    hypothesis=hypothesis,
                    label=label,  # type: ignore[arg-type]
                    label_source="template_truth",
                    family=family,
                    difficulty=difficulty,
                    provenance=Provenance(
                        generator="seed-template-v1",
                        template_id=f"{cid}:{variant}",
                        source_case_id=cid,
                        created_at_utc=_CREATED,
                    ),
                )
            )

    # Content-level dedup (identical premise+hypothesis+label collapse);
    # record_id uniqueness follows automatically via derived ids.
    seen: set[str] = set()
    unique: list[AgentPayIRRecord] = []
    for r in records:
        if r.content_sha256 in seen:
            continue
        seen.add(r.content_sha256)
        unique.append(r)
    records = unique

    out_path = OUT_DIR / "seed_dataset.jsonl"
    out_path.write_text(
        "\n".join(r.model_dump_json() for r in records) + "\n", encoding="utf-8"
    )
    manifest = {
        "format_version": "agentpay-ir-v0.1",
        "dataset_role": "seed (template_truth; splits assigned in P3-M23)",
        "records": len(records),
        "records_before_content_dedup": len(records) + max(0, len(seen) - len(records)),
        "sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(),
        "by_label": _count_by(records, lambda r: r.label),
        "by_difficulty": _count_by(records, lambda r: r.difficulty),
        "families": len({r.family for r in records}),
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    return 0


def _family_for(category: str) -> str:
    mapping = {
        "budget_only": "budget_ceiling",
        "budget_currency_explicit": "currency_binding",
        "currency_binding": "currency_binding",
        "quantity": "quantity_limit",
        "brand_constraint": "brand_identity",
        "alias_handling": "seller_alias",
        "condition_new_required": "condition_new_only",
        "merchant_restriction": "merchant_restriction",
        "recurring_forbidden_explicit": "recurring_forbidden",
        "trial_euphemism": "trial_renewal_trap",
        "membership_resistance": "membership_insertion",
        "bundle_semantic": "bundle_obligation",
        "shipping_fee_semantic": "shipping_fee",
        "delivery_timing_semantic": "delivery_timing",
        "return_policy_semantic": "return_refund",
        "warranty_semantic": "warranty_claim",
        "variant_guard": "variant_mismatch",
        "safe_lookalike_title_trap": "safe_lookalike",
        "safe_lookalike_alias": "safe_lookalike",
        "injection_like_human_text": "injection_resistance",
        "negation_preservation": "condition_new_only",
        "multi_constraint": "budget_ceiling",
        "multi_constraint_variant": "quantity_limit",
        "underspecified_minimal": "budget_ceiling",
        "ambiguous_phrasing": "budget_ceiling",
    }
    return mapping.get(category, "budget_ceiling")


def _count_by(records: list[AgentPayIRRecord], key):  # type: ignore[no-untyped-def]
    out: dict[str, int] = {}
    for r in records:
        k = str(key(r))
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


if __name__ == "__main__":
    raise SystemExit(main())
