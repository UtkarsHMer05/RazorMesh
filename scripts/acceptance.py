"""M50: Phase-1 acceptance run against a LIVE local API (127.0.0.1:8000).

Executes the PRD section 9 demonstration list through real HTTP endpoints and
prints one evidence line per check. Exits non-zero if any check fails.

All flows are LOCAL and SIMULATED (MockPaymentProvider). No production claims.
"""

from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000"
ARTIFACT = Path(__file__).resolve().parents[1] / "docs" / "PHASE1_BENCHMARK.json"
client = httpx.Client(base_url=API, timeout=30.0)

failures: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {name}: {detail}")
    if not ok:
        failures.append(name)


def main() -> int:
    # 0. readiness
    ready = client.get("/ready").json()
    check(
        "readiness",
        ready.get("status") == "ok" and ready.get("mock_payment_provider") is True,
        f"status={ready.get('status')} mock_provider={ready.get('mock_payment_provider')}",
    )

    # 1. normal authorized purchase
    intent = client.post("/buyer/fixture-intent").json()
    intent_id = intent["intent_id"]
    products = client.get("/catalog/products?limit=100").json()["items"]
    product = min(products, key=lambda p: p["price_minor"] + p["shipping_minor"])
    proposal = client.post(
        "/buyer/propose",
        json={
            "intent_id": intent_id,
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
    )
    body = proposal.json()
    check(
        "normal purchase allowed",
        body["decision"] == "ALLOW" and body["ticket_json"] is not None,
        f"decision={body['decision']} total={body['total_minor']} ticket issued",
    )
    execution = client.post(
        "/buyer/execute",
        json={
            "intent_id": intent_id,
            "checkout_id": body["checkout_id"],
            "ticket_json": body["ticket_json"],
            "signature_hex": body["signature_hex"],
        },
    )
    exec_body = execution.json()
    check(
        "execution succeeds once",
        execution.status_code == 200 and exec_body["state"] == "SUCCEEDED",
        f"state={exec_body.get('state')} attempt={exec_body.get('attempt_id', '')[:16]}…",
    )
    first_attempt = exec_body["attempt_id"]

    # 2. replay of the consumed authority collapses idempotently
    replay = client.post(
        "/buyer/execute",
        json={
            "intent_id": intent_id,
            "checkout_id": body["checkout_id"],
            "ticket_json": body["ticket_json"],
            "signature_hex": body["signature_hex"],
        },
    ).json()
    state = client.get(f"/audit/state/{intent_id}").json()
    attempt_rows = state["attempts"]
    check(
        "replay collapses to single effect",
        len(attempt_rows) == 1 and replay["attempt_id"] == first_attempt,
        f"durable attempts={len(attempt_rows)} same_attempt={replay['attempt_id'] == first_attempt}",
    )

    # 3. forged signature cannot execute (no valid ticket -> no provider call)
    forged_intent = client.post("/buyer/fixture-intent").json()
    forged_proposal = client.post(
        "/buyer/propose",
        json={
            "intent_id": forged_intent["intent_id"],
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
    ).json()
    raw = base64.b16decode(forged_proposal["signature_hex"], casefold=True)
    tampered = bytearray(raw)
    tampered[0] ^= 0xFF
    forged_exec = client.post(
        "/buyer/execute",
        json={
            "intent_id": forged_intent["intent_id"],
            "checkout_id": forged_proposal["checkout_id"],
            "ticket_json": forged_proposal["ticket_json"],
            "signature_hex": base64.b16encode(bytes(tampered)).decode().lower(),
        },
    )
    check(
        "forged signature rejected pre-provider",
        forged_exec.status_code == 403
        and forged_exec.json()["detail"]["code"] == "SIGNATURE_INVALID",
        f"http={forged_exec.status_code} code={forged_exec.json()['detail'].get('code')}",
    )

    # 4. twenty concurrent same-ticket attempts -> exactly one provider effect
    conc_intent = client.post("/buyer/fixture-intent").json()
    conc_proposal = client.post(
        "/buyer/propose",
        json={
            "intent_id": conc_intent["intent_id"],
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
    ).json()

    def fire(_: int) -> str:
        res = client.post(
            "/buyer/execute",
            json={
                "intent_id": conc_intent["intent_id"],
                "checkout_id": conc_proposal["checkout_id"],
                "ticket_json": conc_proposal["ticket_json"],
                "signature_hex": conc_proposal["signature_hex"],
            },
        )
        try:
            payload = res.json()
        except json.JSONDecodeError:
            return f"http-{res.status_code}"
        if isinstance(payload, dict):
            return str(payload.get("attempt_id", f"http-{res.status_code}"))
        return f"http-{res.status_code}"

    with ThreadPoolExecutor(max_workers=20) as pool:
        attempt_ids = list(pool.map(fire, range(20)))
    distinct = {a for a in attempt_ids if not a.startswith("http-")}
    conc_state = client.get(f"/audit/state/{conc_intent['intent_id']}").json()
    succeeded_rows = [a for a in conc_state["attempts"] if a["state"] == "SUCCEEDED"]
    check(
        "20-worker same-ticket race -> 1 provider effect",
        len(distinct) == 1
        and len(conc_state["attempts"]) == 1
        and len(succeeded_rows) == 1,
        f"distinct_attempts={len(distinct)} durable={len(conc_state['attempts'])} "
        f"succeeded={len(succeeded_rows)}",
    )

    # 5. attack scenario suite through the real pipeline (server-side)
    lab = client.post("/security-lab/run").json()
    families = {r["family"] for r in lab["results"]}
    check(
        "security-lab suite behaves as designed",
        lab["passed"] == lab["total"] and lab["total"] >= 7,
        f"{lab['passed']}/{lab['total']} scenarios; families={sorted(families)}",
    )

    # 6. audit chain verifies; tamper test detects then self-restores
    verify_before = client.get("/audit/verify").json()
    tamper = client.post("/audit/tamper-test").json()
    verify_after = client.get("/audit/verify").json()
    check(
        "audit chain verifies",
        verify_before["valid"] is True and verify_after["valid"] is True,
        f"before={verify_before['valid']} events={verify_before['events_checked']} "
        f"after_restore={verify_after['valid']}",
    )
    check(
        "tamper test detected",
        tamper.get("detected") is True,
        f"detected={tamper.get('detected')} reason={tamper.get('verdict_reason')}",
    )

    # 7. benchmark artifact exists and reports computed metrics
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    confusion_ok = (
        artifact["confusion"]["FN"] == 0
        and artifact["confusion"]["FP"] == 0
        and artifact["pairs"] >= 6
    )
    check(
        "benchmark metrics from real runner",
        confusion_ok and artifact.get("label", "").startswith("SYNTHETIC"),
        f"pairs={artifact['pairs']} confusion={artifact['confusion']} f1={artifact['f1']}",
    )

    print()
    if failures:
        print(f"ACCEPTANCE FAILED ({len(failures)}): {failures}")
        return 1
    print("ACCEPTANCE PASSED: all live checks green (local, simulated provider only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
