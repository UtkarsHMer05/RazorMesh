"""Pure helpers for the P3-M20 Qwen candidate generator.

The live runner remains a script because it owns rate limiting and persistence.
These helpers keep the security/data semantics deterministic and unit-testable:
stable request identities, diversity-first work ordering, provisional labels,
and complete per-row generator provenance.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from collections.abc import Iterable
from datetime import datetime
from typing import Any, cast

from razormesh_api.agentpay_ir import (
    AgentPayIRRecord,
    Difficulty,
    NliLabel,
    Provenance,
    make_record,
)

GENERATOR_NAME = "qwen3.8-max-free@tokenrouter"
PROMPT_VERSION = "candidate-gen-v2"
BATCH_ID = "phase3-m20-qwen-candidates-v2"
_OOD_FAMILY_PRIORITY = {
    "injection_resistance": 0,
    "safe_lookalike": 1,
    "seller_alias": 2,
    "trial_renewal_trap": 3,
    "membership_insertion": 4,
    "bundle_obligation": 5,
}


def request_key(seed: dict[str, Any]) -> str:
    """Stable across restarts and independent of input ordering."""
    identity = (
        f"{PROMPT_VERSION}|{seed['record_id']}|{seed['family']}|"
        f"{seed['label']}|{seed['difficulty']}"
    )
    return hashlib.sha256(identity.encode()).hexdigest()


def legacy_request_key(seed: dict[str, Any], index: int) -> str:
    """Resolve v1 compact rows during the one-time provenance upgrade."""
    identity = f"candidate-gen-v1|{seed['family']}|{seed['label']}|{seed['difficulty']}|{index}"
    return hashlib.sha256(identity.encode()).hexdigest()


def diversity_first(seeds: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Round-robin family/label/difficulty buckets.

    The old file-order walk generated almost only easy budget examples. This
    schedule makes every prefix diverse, which matters when a free-tier run
    stops early and later resumes.
    """
    unsorted: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    seen_ids: set[str] = set()
    for seed in seeds:
        seed_id = str(seed["record_id"])
        if seed_id in seen_ids:
            continue
        seen_ids.add(seed_id)
        key = (str(seed["family"]), str(seed["label"]), str(seed["difficulty"]))
        unsorted[key].append(seed)

    buckets = {
        key: deque(sorted(rows, key=lambda row: str(row["record_id"])))
        for key, rows in unsorted.items()
    }

    ordered: list[dict[str, Any]] = []
    keys = sorted(
        buckets,
        key=lambda key: (_OOD_FAMILY_PRIORITY.get(key[0], 10), key),
    )
    while keys:
        remaining: list[tuple[str, str, str]] = []
        for key in keys:
            bucket = buckets[key]
            if bucket:
                ordered.append(bucket.popleft())
            if bucket:
                remaining.append(key)
        keys = remaining
    return ordered


def build_record(
    *,
    seed: dict[str, Any],
    premise: str,
    hypothesis: str,
    key: str,
    model_reported: str,
    created_at_utc: datetime,
    prompt_version: str = PROMPT_VERSION,
    batch_id: str = BATCH_ID,
) -> AgentPayIRRecord:
    """Build one schema-validated provisional row with complete provenance."""
    return make_record(
        record_id="air_" + hashlib.sha256(key.encode()).hexdigest()[:26].upper(),
        premise=premise,
        hypothesis=hypothesis,
        label=cast("NliLabel", seed["label"]),
        label_source="qwen_provisional",
        family=seed["family"],
        difficulty=cast("Difficulty", seed["difficulty"]),
        provenance=Provenance(
            generator=GENERATOR_NAME,
            generator_model=model_reported,
            prompt_version=prompt_version,
            batch_id=batch_id,
            source_case_id=seed["record_id"],
            created_at_utc=created_at_utc,
            generator_request_id=key,
        ),
    )
