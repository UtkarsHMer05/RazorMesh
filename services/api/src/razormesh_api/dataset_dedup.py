"""P3-M22: exact + near-duplicate detection for AgentPay-IR pools.

- Exact duplicates: identical content_sha256.
- Near duplicates: token-set Jaccard similarity over
  (premise_tokens UNION hypothesis_tokens), computed WITHIN the same
  (family, label) class — cross-class collisions are reported separately as
  cross_class_collisions because they usually indicate mislabeling rather
  than duplication.

Clusters are resolved deterministically: the lexicographically smallest
record_id in a cluster is canonical; every other member records
``duplicate_of``. Pure functions, no I/O, deterministic output order.
"""

from dataclasses import dataclass

from razormesh_api.agentpay_ir import AgentPayIRRecord


@dataclass(frozen=True)
class DedupReport:
    canonical_ids: frozenset[str]
    duplicate_of: dict[str, str]
    clusters: tuple[tuple[str, ...], ...]
    cross_class_collisions: tuple[tuple[str, str], ...]


def _tokens(record: AgentPayIRRecord) -> frozenset[str]:
    blob = f"{record.premise} {record.hypothesis}".lower()
    return frozenset(w for w in blob.split() if len(w) > 2)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / len(a | b)


def analyze(
    records: list[AgentPayIRRecord],
    *,
    near_threshold: float = 0.90,
) -> DedupReport:
    # ---- exact ------------------------------------------------------------
    by_hash: dict[str, list[AgentPayIRRecord]] = {}
    for r in records:
        by_hash.setdefault(r.content_sha256, []).append(r)

    duplicate_of: dict[str, str] = {}
    clusters: list[tuple[str, ...]] = []
    for group in by_hash.values():
        ordered = sorted(group, key=lambda r: r.record_id)
        canonical = ordered[0].record_id
        clusters.append(tuple(sorted(r.record_id for r in group)))
        for dup in ordered[1:]:
            duplicate_of[dup.record_id] = canonical

    # ---- near (within same family+label, not already exact dups) ----------
    unique = [r for r in records if r.record_id not in duplicate_of]
    tokens = {r.record_id: _tokens(r) for r in unique}

    uf: dict[str, str] = {}

    def find(x: str) -> str:
        while uf.setdefault(x, x) != x:
            x = uf[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            lo, hi = sorted((ra, rb))
            uf[hi] = lo

    cross_class: list[tuple[str, str]] = []
    for i, a in enumerate(unique):
        for b in unique[i + 1 :]:
            sim = _jaccard(tokens[a.record_id], tokens[b.record_id])
            if sim < near_threshold:
                continue
            if (a.family, a.label) == (b.family, b.label):
                union(a.record_id, b.record_id)
            else:
                pair = tuple(sorted((a.record_id, b.record_id)))
                cross_class.append((str(pair[0]), str(pair[1])))

    # near-dup clusters -> duplicate_of against canonical (smallest id)
    groups_by_root: dict[str, list[str]] = {}
    for member_id in uf:
        groups_by_root.setdefault(find(member_id), []).append(member_id)
    for group_members in groups_by_root.values():
        if len(group_members) < 2:
            continue
        ordered_ids = sorted(group_members)
        clusters.append(tuple(ordered_ids))
        canonical_id = ordered_ids[0]
        for member_id in ordered_ids[1:]:
            if member_id not in duplicate_of:
                duplicate_of[member_id] = canonical_id

    canonical_ids = frozenset(
        record.record_id for record in unique if record.record_id not in duplicate_of
    )
    return DedupReport(
        canonical_ids=canonical_ids,
        duplicate_of=duplicate_of,
        clusters=tuple(sorted(clusters)),
        cross_class_collisions=tuple(cross_class),
    )
