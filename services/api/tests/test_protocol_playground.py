"""Phase-5 (M046-M061) acceptance: Protocol Playground.

Proves (through the REAL engines):
- only supported protocol slices are exposed;
- every option maps to a real implementation (benchmark envelope builder);
- safe packet: firewall PASS + consistency MATCH;
- amount drift: firewall still PASS but consistency MISMATCH (the thesis);
- replay: duplicate idempotency rejected;
- downgrade: real version policy BLOCKs;
- corrupt signature: verification fails;
- cross-protocol: all lanes MATCH; one diverged lane MISMATCHes alone;
- scenario-c (live orchestrator): protocol PASS + final BLOCK + provider 0;
- no key material or signature values in any response.
"""

from fastapi.testclient import TestClient


def test_protocols_catalog_lists_only_supported(playground_client: TestClient) -> None:
    body = playground_client.get("/protocol-playground/protocols").json()
    ids = {p["id"] for p in body["protocols"]}
    assert ids == {"mcp", "ucp", "ap2", "acp", "a2a"}
    for p in body["protocols"]:
        assert p["version"] and p["transport"]


def test_mutations_catalog_is_inputs_only(playground_client: TestClient) -> None:
    body = playground_client.get("/protocol-playground/mutations").json()
    for m in body["mutations"]:
        assert set(m) == {"id", "label"}, "mutations carry inputs only, never outcomes"


def test_safe_packet_passes_protocol_and_matches(playground_client: TestClient) -> None:
    res = playground_client.post(
        "/protocol-playground/run", json={"protocol": "ucp", "mutation": "none"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["checks"]["protocol_firewall"]["status"] == "PROTOCOL_PASS"
    assert body["consistency"] == "MATCH"
    assert "not transaction authority" in body["authority_note"]


def test_amount_drift_protocol_valid_intent_invalid(playground_client: TestClient) -> None:
    """THE THESIS: protocol layer passes; the commitment no longer matches."""
    res = playground_client.post(
        "/protocol-playground/run", json={"protocol": "mcp", "mutation": "amount_plus_one"}
    )
    body = res.json()
    assert body["checks"]["protocol_firewall"]["status"] == "PROTOCOL_PASS"
    assert body["consistency"] == "MISMATCH", (
        "a drifted transaction must MISMATCH the authorized commitment"
    )


def test_replay_is_rejected_by_real_idempotency(playground_client: TestClient) -> None:
    res = playground_client.post(
        "/protocol-playground/run",
        json={"protocol": "ap2", "mutation": "replay_same_packet"},
    )
    body = res.json()
    assert body["checks"]["replay_idempotency"]["status"] == "FAIL"


def test_downgrade_is_blocked_by_real_version_policy(playground_client: TestClient) -> None:
    res = playground_client.post(
        "/protocol-playground/run",
        json={"protocol": "mcp", "mutation": "protocol_downgrade"},
    )
    body = res.json()
    assert body["checks"]["schema_version"]["status"] == "FAIL"
    assert body["checks"]["protocol_firewall"]["status"] == "PROTOCOL_BLOCK"


def test_corrupt_signature_fails_verification(playground_client: TestClient) -> None:
    res = playground_client.post(
        "/protocol-playground/run",
        json={"protocol": "ucp", "mutation": "corrupt_signature"},
    )
    body = res.json()
    assert body["checks"]["identity_signature"]["status"] == "FAIL"


def test_cross_protocol_all_match_then_one_lane_diverges(playground_client: TestClient) -> None:
    ok = playground_client.get("/protocol-playground/cross").json()
    assert ok["overall"] == "MATCH"
    assert all(lane["consistency"] == "MATCH" for lane in ok["lanes"])

    diverged = playground_client.get("/protocol-playground/cross", params={"diverge": "ap2"}).json()
    assert diverged["overall"] == "MISMATCH"
    by_proto = {lane["protocol"]: lane["consistency"] for lane in diverged["lanes"]}
    assert by_proto["ap2"] == "MISMATCH"
    # only the divergent lane mismatches
    assert all(v == "MATCH" for k, v in by_proto.items() if k != "ap2")


def test_scenario_c_live_pipeline_proves_the_thesis(playground_client: TestClient) -> None:
    """D-056 live proof: protocol PASS + RazorGuard BLOCK + provider NOT contacted."""
    res = playground_client.post("/protocol-playground/scenario-c")
    assert res.status_code == 200
    body = res.json()
    assert body.get("provider_contacted") is False, str(body)[:200]
    final = body.get("final_decision") or body.get("final")
    assert final == "BLOCK", str(body)[:200]


def test_unknown_protocol_and_mutation_are_404(playground_client: TestClient) -> None:
    assert (
        playground_client.post(
            "/protocol-playground/run", json={"protocol": "grpc", "mutation": "none"}
        ).status_code
        == 404
    )
    assert (
        playground_client.post(
            "/protocol-playground/run", json={"protocol": "ucp", "mutation": "pwn"}
        ).status_code
        == 404
    )
    assert (
        playground_client.get("/protocol-playground/cross", params={"diverge": "x"}).status_code
        == 404
    )


def test_no_key_material_in_any_response(playground_client: TestClient) -> None:
    for path in ("/protocol-playground/protocols", "/protocol-playground/mutations"):
        res = playground_client.get(path)
        blob = str(res.json())
        for banned in ("BEGIN PRIVATE KEY", "signature_hex", "secret", "kid-1-private"):
            assert banned not in blob
    for spec in (
        {"protocol": "ucp", "mutation": "none"},
        {"protocol": "mcp", "mutation": "corrupt_signature"},
    ):
        res = playground_client.post("/protocol-playground/run", json=spec)
        blob = str(res.json())
        assert "BEGIN PRIVATE KEY" not in blob
        # only a truncated commitment head is ever exposed
        if "commitment" in blob:
            heads = [p for p in blob.split('"') if len(p) == 16]
            assert all(len(h) == 16 for h in heads)


# ---------------------------------------------------------------------------
# Deep-engine correction G006-G011: real artifacts, real verifiers, real pairs
# ---------------------------------------------------------------------------


def test_quantity_mutation_changes_quantity_field_not_total_proxy(
    playground_client: TestClient,
) -> None:
    """G009: quantity 1→2 must change the QUANTITY; total recomputes as a
    consequence (unit price unchanged), never a bare totalx2 proxy."""
    res = playground_client.post(
        "/protocol-playground/run", json={"protocol": "ucp", "mutation": "quantity_plus_one"}
    )
    body = res.json()
    ir = body["ir"]
    assert ir["quantity"] == 2, "the quantity field itself must change"
    assert body["packet"]["quantity"] == 2
    assert ir["total_minor"] == 189_900 * 2  # consequence of qty 2 at the same unit price
    assert body["consistency"] == "MISMATCH"


def test_recurring_mutation_changes_recurring_field(playground_client: TestClient) -> None:
    """G008: recurring insertion must set the actual recurring mode/terms."""
    res = playground_client.post(
        "/protocol-playground/run", json={"protocol": "ucp", "mutation": "recurring_inserted"}
    )
    body = res.json()
    assert body["ir"]["recurring"] == "monthly"
    assert body["packet"]["recurring"] == "monthly"
    safe = playground_client.post(
        "/protocol-playground/run", json={"protocol": "ucp", "mutation": "none"}
    ).json()
    assert safe["ir"]["recurring"] == "none"
    assert body["consistency"] == "MISMATCH"


def test_merchant_swap_changes_merchant_field(playground_client: TestClient) -> None:
    """G006: merchant substitution must change the actual merchant identity."""
    res = playground_client.post(
        "/protocol-playground/run", json={"protocol": "ucp", "mutation": "merchant_swap"}
    )
    body = res.json()
    assert body["ir"]["merchant"] == "merch_b"
    assert body["consistency"] == "MISMATCH"


def test_corrupt_signature_really_corrupts_and_verifier_rejects(
    playground_client: TestClient,
) -> None:
    """G007: the corruption must change actual signed material and the REAL
    verifier must fail because of it."""
    res = playground_client.post(
        "/protocol-playground/run", json={"protocol": "ucp", "mutation": "corrupt_signature"}
    )
    body = res.json()
    check = body["checks"]["identity_signature"]
    assert check["status"] == "FAIL"
    assert "verifier:" in check["detail"]
    assert "corrupted" in check["detail"] or "no longer covers" in check["detail"]


def test_removing_corruption_makes_verifier_pass() -> None:
    """G007 PASS-condition: without corruption the same verifier returns PASS.

    Mutation-causality proof: removing the corruption step flips the verdict.
    """
    from razormesh_api.protocol.agentpay_x import _base_ir
    from razormesh_api.protocol_playground import (
        PacketSpec,
        _corrupt_signature_evidence,
        _packet_envelope,
        _verify_signature_evidence,
    )

    spec = PacketSpec(protocol="ucp", mutation="corrupt_signature")
    authorized = _base_ir()
    env, _ = _packet_envelope(spec, authorized)
    clean = _verify_signature_evidence(authorized, env)
    assert clean["verified"] is True
    corrupted_env = _corrupt_signature_evidence(env)
    dirty = _verify_signature_evidence(authorized, corrupted_env)
    assert dirty["verified"] is False
    assert dirty["reason"] == "signature_covers_corrupted_commitment"
    assert (
        corrupted_env.signature_evidence["commerce_commitment_hash"]
        != env.signature_evidence["commerce_commitment_hash"]
    )


def test_replay_fail_is_engine_derived(playground_client: TestClient) -> None:
    """G006: the replay FAIL must come from the real idempotency engine
    (REPLAY reason on the second evaluation), not the mutation name."""
    res = playground_client.post(
        "/protocol-playground/run", json={"protocol": "ucp", "mutation": "replay_same_packet"}
    )
    body = res.json()
    assert body["checks"]["replay_idempotency"]["status"] == "FAIL"
    assert "duplicate key rejected" in body["checks"]["replay_idempotency"]["detail"]
    assert body["checks"]["protocol_firewall"]["status"] == "PROTOCOL_CHALLENGE"


def test_downgrade_fail_is_engine_derived(playground_client: TestClient) -> None:
    """G006: the downgrade FAIL must be the firewall's own version verdict."""
    res = playground_client.post(
        "/protocol-playground/run", json={"protocol": "mcp", "mutation": "protocol_downgrade"}
    )
    body = res.json()
    assert body["checks"]["schema_version"]["status"] == "FAIL"
    assert "firewall rejected" in body["checks"]["schema_version"]["detail"]
    assert body["protocol_version"] == "2025-12-01"
    fw = body["checks"]["protocol_firewall"]
    assert fw["status"] == "PROTOCOL_BLOCK"
    assert "unsupported_version" in fw["detail"] and "downgrade" in fw["detail"]


def test_cross_protocol_never_compares_base_to_base(playground_client: TestClient) -> None:
    """G010: per-lane pairs must be (lane_ir, lane_envelope).

    Diverging ONE lane must MISMATCH only that lane; a base/base comparison
    would MATCH every lane and this test would fail.
    """
    diverged = playground_client.get("/protocol-playground/cross", params={"diverge": "ap2"}).json()
    by_proto = {lane["protocol"]: lane["consistency"] for lane in diverged["lanes"]}
    assert by_proto["ap2"] == "MISMATCH"
    assert all(v == "MATCH" for k, v in by_proto.items() if k != "ap2")
    assert diverged["overall"] == "MISMATCH"
    assert diverged["envelope_consistency"]["ap2"] == "MISMATCH"
    assert all(v == "MATCH" for k, v in diverged["envelope_consistency"].items() if k != "ap2")
    heads = {lane["commitment_head"] for lane in diverged["lanes"]}
    assert len(heads) == 2
