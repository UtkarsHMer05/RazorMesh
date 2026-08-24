"""M49: local performance/resource baseline (LOCAL ONLY — no production claims).

Measures, on this machine, with this exact dependency set:

A. Pure-CPU micro latencies (no network/DB/Redis):
   - checkout authorization hash (JCS projection + SHA-256)
   - intent authorization hash
   - Ed25519 execution-ticket issue (canonicalize + sign)
   - ordered fail-closed ticket verify (signature + 11 bindings)
   - RazorGuard deterministic decide() over all rule groups
B. End-to-end happy-path execution through the real trusted core
   (propose -> authorize -> reserve -> nonce claim -> mock provider),
   including PostgreSQL + Redis round trips.
C. Paired safe/unsafe benchmark wall-clock (one pair per unsafe family).
D. In-process API latency over ASGI transport (excludes network stack).

Results are written to docs/PHASE1_PERFORMANCE.json with hardware/runtime
context. All numbers describe THIS local prototype only.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from importlib import metadata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "api" / "src"))

from razormesh_api.api.main import app
from razormesh_api.benchmark import PairedBenchmark
from razormesh_api.catalog import seed_catalog
from razormesh_api.checkout_service import CheckoutService, ProposedItem
from razormesh_api.decider import DecisionEngine
from razormesh_api.domain.authz_hash import (
    checkout_authorization_hash,
    intent_authorization_hash,
)
from razormesh_api.domain.ids import (
    DecisionId,
    ExecutionTicketId,
    IntentId,
    new_ulid,
)
from razormesh_api.evaluation import AdversarialRunner
from razormesh_api.executor import TrustedPaymentExecutor
from razormesh_api.keys import DevKeyPair, DevSigningKeys
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.nonce import NonceRegistry
from razormesh_api.persistence.models import IntentContract as RowIntent
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.providers.mock import MockMode, MockPaymentProvider
from razormesh_api.rules.catalog_rules import CATALOG_RULES
from razormesh_api.rules.engine import EvaluationContext, ProductFacts
from razormesh_api.rules.money_rules import MONEY_RULES
from razormesh_api.rules.policy_rules import POLICY_RULES
from razormesh_api.spend import SpendManager
from razormesh_api.tickets import (
    CurrentBinding,
    ExecutionTicketClaims,
    TicketIssuer,
    TicketVerifier,
)


def _stats(samples_ms: list[float]) -> dict[str, float | int]:
    ordered = sorted(samples_ms)
    n = len(ordered)

    def pct(q: float) -> float:
        return round(ordered[min(n - 1, round(q * (n - 1)))], 4)

    return {
        "n": n,
        "mean_ms": round(sum(ordered) / n, 4),
        "p50_ms": pct(0.50),
        "p95_ms": pct(0.95),
        "min_ms": round(ordered[0], 4),
        "max_ms": round(ordered[-1], 4),
    }


def _bench(
    fn: Callable[[], object], *, n: int, warmup: int = 25
) -> dict[str, float | int]:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(n):
        start = time.perf_counter_ns()
        fn()
        samples.append((time.perf_counter_ns() - start) / 1e6)
    return _stats(samples)


class Harness:
    """Wires the real trusted core once; resets durable state per iteration."""

    def __init__(self) -> None:
        runner = AdversarialRunner()
        self.repos: Repositories = runner.repositories
        self.keys: DevKeyPair = DevSigningKeys(
            private_path="infra/keys/dev_ticket_ed25519_private.pem",
            public_path="infra/keys/dev_ticket_ed25519_public.pem",
        ).ensure()

    def reset_with_intent(self) -> IntentId:
        from sqlalchemy import text as sa_text

        wipe_statements = (
            "DELETE FROM execution_attempts",
            "DELETE FROM execution_tickets",
            "DELETE FROM decisions",
            "DELETE FROM authorization_spend",
            "DELETE FROM checkouts",
            "DELETE FROM intent_contracts",
        )
        with self.repos.transaction() as session:
            for stmt in wipe_statements:
                session.execute(sa_text(stmt))
        seed_catalog(self.repos)

        iid = IntentId.generate()
        product = min(self.repos.products.list(limit=100), key=lambda p: p.price_minor)
        payable = product.price_minor + product.shipping_minor
        now = datetime.now(UTC)
        with self.repos.transaction() as session:
            session.merge(
                RowIntent(
                    intent_id=str(iid),
                    principal_id=f"usr_{new_ulid()}",
                    agent_id=f"agt_{new_ulid()}",
                    authorization_generation=1,
                    status="AUTHORIZED",
                    currency="INR",
                    recurring_allowed=False,
                    max_total_minor=10_000_000,
                    aggregate_budget_minor=50_000_000,
                    max_quantity=1,
                    approval_threshold_minor=payable,
                    issued_at=now,
                    authorized_at=now,
                    expires_at=now + timedelta(minutes=30),
                    created_at=now,
                    updated_at=now,
                )
            )
        return iid

    def service(self) -> CheckoutService:
        ledger = EvidenceLedger(self.repos)
        engine = DecisionEngine([*MONEY_RULES, *CATALOG_RULES, *POLICY_RULES])
        return CheckoutService(
            repos=self.repos, ledger=ledger, engine=engine, keys=self.keys
        )

    def executor(self) -> TrustedPaymentExecutor:
        return TrustedPaymentExecutor(
            repos=self.repos,
            keys=self.keys,
            nonces=self.nonces(),
            provider=MockPaymentProvider(mode=MockMode.SUCCESS),
            spend=SpendManager(self.repos),
        )

    @staticmethod
    def nonces() -> NonceRegistry:
        import os

        from redis import Redis

        url = os.environ.get("RAZORMESH_TEST_REDIS_URL", "redis://127.0.0.1:16379/0")
        return NonceRegistry(
            Redis.from_url(url, decode_responses=True), ttl_seconds=120
        )


def micro_benchmarks(harness: Harness) -> dict[str, dict[str, float | int]]:
    from razormesh_api.revalidation import domain_intent_from_row

    iid = harness.reset_with_intent()
    svc = harness.service()
    product = min(harness.repos.products.list(limit=100), key=lambda p: p.price_minor)
    proposal = svc.propose(intent_id=iid, items=[ProposedItem(product.id)])
    row_intent = harness.repos.intents.get(iid)
    if row_intent is None:
        raise RuntimeError("intent fixture missing")
    contract = domain_intent_from_row(row_intent)
    env = proposal.envelope

    facts: dict[str, ProductFacts] = {}
    for item in env.line_items:
        row = harness.repos.products.get(item.product_id)
        if row is not None:
            facts[item.product_id.value] = ProductFacts(
                brand=row.brand, category=row.category
            )

    ctx = EvaluationContext(
        intent=contract,
        checkout=env,
        committed_minor=0,
        reserved_minor=0,
        now_utc=datetime.now(UTC),
        product_facts=facts,
    )

    now = datetime.now(UTC)
    claims = ExecutionTicketClaims(
        ticket_id=ExecutionTicketId.generate(),
        decision_id=DecisionId.generate(),
        checkout_id=env.checkout_id,
        intent_id=contract.intent_id,
        principal_id=str(contract.principal_id),
        agent_id=str(contract.agent_id),
        authorization_generation=contract.authorization_generation,
        intent_hash=proposal.intent_hash,
        checkout_hash=proposal.checkout_hash,
        checkout_revision=env.revision,
        merchant_id=str(env.merchant_id),
        amount_minor=env.compute_total().amount_minor,
        currency=contract.currency,
        policy_version="razormesh-phase1-policy-v1",
        nonce=f"nonce-{new_ulid()}{new_ulid()}",
        issued_at=now,
        expires_at=now + timedelta(seconds=120),
    )

    issuer = TicketIssuer(harness.keys)
    signed = issuer.issue(claims)
    verifier = TicketVerifier(harness.keys)
    binding = CurrentBinding(
        principal_id=claims.principal_id,
        agent_id=claims.agent_id,
        intent_id=claims.intent_id.value,
        intent_hash=claims.intent_hash,
        authorization_generation=claims.authorization_generation,
        checkout_id=claims.checkout_id.value,
        checkout_hash=claims.checkout_hash,
        checkout_revision=claims.checkout_revision,
        merchant_id=claims.merchant_id,
        amount_minor=claims.amount_minor,
        currency=claims.currency,
    )
    engine = DecisionEngine([*MONEY_RULES, *CATALOG_RULES, *POLICY_RULES])

    return {
        "checkout_authz_hash_jcs_sha256": _bench(
            lambda: checkout_authorization_hash(env), n=3000
        ),
        "intent_authz_hash_jcs_sha256": _bench(
            lambda: intent_authorization_hash(contract), n=3000
        ),
        "ticket_issue_canonicalize_and_sign": _bench(
            lambda: issuer.issue(claims), n=2000
        ),
        "ticket_verify_signature_and_bindings": _bench(
            lambda: verifier.verify(signed, binding), n=2000
        ),
        "razorguard_decide_all_rule_groups": _bench(
            lambda: engine.decide(intent=contract, checkout=env, ctx=ctx), n=2000
        ),
    }


def e2e_benchmark(harness: Harness, iterations: int = 25) -> dict[str, object]:
    samples: list[float] = []
    product = min(harness.repos.products.list(limit=100), key=lambda p: p.price_minor)
    for _ in range(iterations):
        iid = harness.reset_with_intent()
        svc = harness.service()
        executor = harness.executor()
        start = time.perf_counter_ns()
        proposal = svc.propose(intent_id=iid, items=[ProposedItem(product.id)])
        authz = svc.authorize(intent_id=iid, proposal=proposal)
        if authz.signed_ticket is None or authz.binding is None:
            raise RuntimeError(
                f"expected ALLOW for fixture: {authz.outcome.reason_codes}"
            )
        attempt = executor.execute(
            signed_ticket=authz.signed_ticket,
            binding=authz.binding,
            intent_id=iid,
            now_utc=datetime.now(UTC),
        )
        elapsed_ms = (time.perf_counter_ns() - start) / 1e6
        if attempt.state != "SUCCEEDED":
            raise RuntimeError(f"expected SUCCEEDED, got {attempt.state}")
        samples.append(elapsed_ms)
    return {
        "trusted_core_happy_path_propose_authorize_execute": _stats(samples),
        "includes": "PostgreSQL persistence + Redis nonce claim + mock provider effect",
    }


def api_benchmark() -> dict[str, object]:
    from fastapi.testclient import TestClient

    results: dict[str, object] = {}
    with TestClient(app) as client:
        client.get("/ready")
        results["api_get_health"] = {
            **_bench(lambda: client.get("/health").status_code, n=300),
            "note": "in-process ASGI transport; excludes network stack",
        }
        results["api_get_catalog_products_limit100"] = {
            **_bench(
                lambda: client.get("/catalog/products?limit=100").status_code, n=200
            ),
            "note": "in-process ASGI transport; excludes network stack",
        }
        results["api_post_buyer_fixture_intent"] = {
            **_bench(lambda: client.post("/buyer/fixture-intent").status_code, n=40),
            "note": "in-process ASGI transport; excludes network stack; writes durable intent",
        }
    return results


def hardware_context() -> dict[str, object]:
    def sysctl(name: str) -> str | None:
        try:
            out = subprocess.run(
                ["sysctl", "-n", name], capture_output=True, text=True, check=False
            )
            return out.stdout.strip() or None
        except OSError:
            return None

    package_versions: dict[str, str] = {}
    for pkg in (
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "alembic",
        "cryptography",
        "rfc8785",
        "uvicorn",
    ):
        try:
            package_versions[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            package_versions[pkg] = "unknown"

    memory_raw = sysctl("hw.memsize")
    return {
        "label": "LOCAL-ONLY Phase-1 baseline; NOT production capacity",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": sysctl("machdep.cpu.brand_string"),
        "memory_bytes": int(memory_raw)
        if memory_raw and memory_raw.isdigit()
        else None,
        "logical_cpus": os.cpu_count(),
        "python_version": sys.version.split()[0],
        "package_versions": package_versions,
        "measured_at_utc": datetime.now(UTC).isoformat(),
    }


def main() -> int:
    print("== RazorMesh Phase-1 local performance baseline ==")
    harness = Harness()
    report: dict[str, object] = {"context": hardware_context()}
    print("[1/4] pure-CPU micro latencies…")
    report["micro"] = micro_benchmarks(harness)
    print("[2/4] end-to-end trusted-core happy path…")
    report["end_to_end"] = e2e_benchmark(harness)
    print("[3/4] paired benchmark wall-clock…")
    start = time.perf_counter_ns()
    bench_report = PairedBenchmark().run()
    bench_seconds = (time.perf_counter_ns() - start) / 1e9
    report["benchmark_suite"] = {
        "wall_seconds": round(bench_seconds, 3),
        "pairs": bench_report.pairs,
        "confusion": {
            "TP": bench_report.tp,
            "FP": bench_report.fp,
            "TN": bench_report.tn,
            "FN": bench_report.fn,
        },
        "precision": round(bench_report.precision, 4),
        "recall": round(bench_report.recall, 4),
        "f1": round(bench_report.f1, 4),
        "note": "14 unsafe/safe pairs (28 isolated real-pipeline scenario executions)",
    }
    print("[4/4] in-process API latency…")
    report["api_asgi_inprocess"] = api_benchmark()

    out = REPO_ROOT / "docs" / "PHASE1_PERFORMANCE.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"artifact written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
