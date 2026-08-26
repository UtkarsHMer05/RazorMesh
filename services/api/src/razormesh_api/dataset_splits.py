"""P3-M23: deterministic, group-based, leakage-safe dataset splitting.

Groups come from ``provenance.source_case_id`` (records derived from the same
seed case MUST NOT straddle splits) falling back to ``record_id`` for
standalone rows. Assignment is deterministic: a stable SHA256 hash of the
group id picks the split, then label-stratification is approximated by
assigning whole GROUPS only (never individual rows), which structurally
prevents pair/template leakage.

``leakage_report`` is the release-blocking gate: it FAILS if any group appears
in more than one split or if any split lost its label diversity entirely.
"""

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass

from razormesh_api.agentpay_ir import AgentPayIRRecord

SPLITS: tuple[str, str, str] = ("train", "val", "test")


def _group_of(record: AgentPayIRRecord) -> str:
    return record.provenance.source_case_id or record.record_id


def _split_for_group(group_id: str) -> str:
    digest = hashlib.sha256(f"razormesh-split-v1:{group_id}".encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "val"
    return "test"


@dataclass(frozen=True)
class SplitReport:
    assigned: int
    counts: dict[str, int]
    labels_by_split: dict[str, dict[str, int]]
    leaked_groups: tuple[str, ...]
    empty_label_splits: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.leaked_groups and not self.empty_label_splits


def assign_splits(records: list[AgentPayIRRecord]) -> list[AgentPayIRRecord]:
    """Return NEW record objects with ``split`` set (frozen models copied)."""
    out: list[AgentPayIRRecord] = []
    for r in records:
        out.append(r.model_copy(update={"split": _split_for_group(_group_of(r))}))
    return out


def leakage_report(records: list[AgentPayIRRecord]) -> SplitReport:
    """Detect any group spanning multiple splits + any label-empty split."""
    group_splits: dict[str, set[str]] = defaultdict(set)
    counts: Counter[str] = Counter()
    labels_by_split: dict[str, Counter[str]] = {
        **{s: Counter() for s in SPLITS},
        "UNASSIGNED": Counter(),
    }

    for r in records:
        split = r.split or "UNASSIGNED"
        group_splits[_group_of(r)].add(split)
        counts[split] += 1
        labels_by_split[split][r.label] += 1

    leaked = tuple(
        sorted(g for g, splits in group_splits.items() if len(splits - {"UNASSIGNED"}) > 1)
    )
    empty = tuple(s for s in SPLITS if not any(labels_by_split[s].values()))
    return SplitReport(
        assigned=len([r for r in records if r.split]),
        counts=dict(counts),
        labels_by_split={s: dict(c) for s, c in labels_by_split.items()},
        leaked_groups=leaked,
        empty_label_splits=empty,
    )


def assert_no_leakage(records: list[AgentPayIRRecord]) -> SplitReport:
    """Release-blocking assertion helper (raises AssertionError on leakage)."""
    report = leakage_report(records)
    assert report.passed, (
        f"leakage detected: leaked_groups={report.leaked_groups} "
        f"empty_label_splits={report.empty_label_splits}"
    )
    return report
