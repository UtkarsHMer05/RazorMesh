# Protocol Playground Truth Table (Deep Engine Correction G011)

One row per playground control. Every displayed check is derived by running a
real engine over a real artifact; the only UI-side timing is the ordered
reveal pacing (explicitly labeled as pacing over an already-complete backend
result — never a fake wait on outcomes).

Legend for "Artifact" — what the mutation actually changes:
- `IR(total)` = the canonical IR's totals.total_minor (commitment changes)
- `IR(quantity)` = the IR item's quantity field (total recomputes as a consequence)
- `IR(recurring)` = the IR's recurring mode/terms
- `IR(merchant)` = the IR's merchant identity
- `ENV(version)` = the packet envelope's source_protocol_version
- `ENV(sig_evidence)` = the commitment hash bound in the envelope's signature evidence

| Control | User input | Generated artifact | Real verifier | Displayed check | Real consistency |
|---|---|---|---|---|---|
| Safe packet (none) | protocol choice | authorized IR + envelope bound to the authorized commitment | `evaluate_envelope` → PROTOCOL_PASS; `_verify_signature_evidence` → verified | PASS ×4 | `compare_ir_to_envelope` → MATCH |
| Amount +1 | protocol choice | IR(total 189900→189901) | firewall PASS (packet is protocol-valid); signature verifier FAIL — the envelope's signed commitment covers the AUTHORIZED IR, not this one | sig FAIL; fw PASS | MISMATCH (commitment differs) |
| Amount +₹500 | protocol choice | IR(total 189900→239900) | same as +1 | sig FAIL; fw PASS | MISMATCH |
| Quantity +1 | protocol choice | IR(quantity 1→2; unit price unchanged; total recomputes ×2 as consequence) | firewall PASS; signature verifier FAIL | sig FAIL; fw PASS | MISMATCH (the quantity is commitment-relevant) |
| Recurring inserted | protocol choice | IR(recurring none→monthly, interval 1m) | firewall PASS; signature verifier FAIL | sig FAIL; fw PASS | MISMATCH (recurring is commitment-relevant) |
| Merchant swap | protocol choice | IR(merchant merch_a→merch_b) | firewall PASS; signature verifier FAIL | sig FAIL; fw PASS | MISMATCH |
| Corrupt signature/digest | protocol choice | ENV(sig_evidence): the bound commitment hash is actually re-hashed (bytes flipped); a `corruption` marker records the field | `_verify_signature_evidence` re-derives the IR commitment and compares → NOT verified, reason `signature_covers_corrupted_commitment` | identity_signature FAIL (verifier-derived, with reason) | MISMATCH (evidence no longer matches any IR) |
| Replay same packet | protocol choice | same envelope, same idempotency key fed to the firewall a second time | `evaluate_envelope` with `seen_recent_keys` → PROTOCOL_CHALLENGE with reason `replay` | replay FAIL ("duplicate key rejected on second evaluation"); fw PROTOCOL_CHALLENGE | MATCH (the packet itself is unchanged) |
| Protocol downgrade | protocol choice | ENV(version) actually downgraded (e.g. MCP 2026-07-28 → 2025-12-01) | `evaluate_envelope` → PROTOCOL_BLOCK, reasons `unsupported_version; downgrade` | schema_version FAIL ("firewall rejected…"); fw PROTOCOL_BLOCK | MATCH (semantics unchanged) |
| Cross-protocol (all true) | lane buttons | 5 envelopes, each bound to the authorized IR's commitment; every lane's IR = authorized IR | per-lane `compare_ir_to_envelope(lane_ir, lane_env)` + IR-vs-IR `equal_under_commitment(base, lane_ir)` | all lanes MATCH | MATCH |
| Cross-protocol (diverge X) | lane buttons | only lane X's IR mutates (total +1); its envelope still carries the authorized commitment; other lanes untouched | per-lane real comparisons — pairs are (lane_ir, lane_envelope), never (base, base) | only lane X MISMATCH; others MATCH; overall MISMATCH | lane X MISMATCH |

## Verifier inventory (no painted results remain)

| Check displayed | Engine that produces it |
|---|---|
| schema/version | protocol firewall version policy (`evaluate_envelope` reasons: `unsupported_version`/`downgrade`) |
| identity/signature | `_verify_signature_evidence` — re-derives the IR commitment and compares against the envelope's signed evidence |
| replay/idempotency | protocol firewall idempotency policy (REPLAY reason on second evaluation of the same key) |
| protocol firewall | `evaluate_envelope` (the Phase-4 firewall) |
| consistency | `compare_ir_to_envelope` / `equal_under_commitment` (Phase-4 consistency engine) |
| commitment head | `commitment_hash(IR)` (truncated; no key material) |

Test enforcement: `tests/test_protocol_playground.py` (19 tests) — including
`test_removing_corruption_makes_verifier_pass` (mutation-causality: without
the corruption step the same verifier returns PASS, so the test would fail if
the corruption were fake) and `test_cross_protocol_never_compares_base_to_base`
(a base/base comparison would MATCH every lane; the test fails in that case).
