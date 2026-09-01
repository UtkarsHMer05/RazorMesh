# M001 — micro-fix baseline (2026-09-01)

- HEAD: 5c61ffa939539ced369dc826ab80f23e1b8d4f6a (clean tree)
- semantic demo (live): razorguard ALLOW / semantic BLOCK / fusion BLOCK /
  ticket NOT ISSUED / attempt NOT CREATED / provider 0 (R002 truth preserved)
- demo intent: intent_01M1E4V6W73KAY0QRHJMWJ3Q2S
- demo checkout REPORTED: chk_01M1E4V6Y5Q0HNYNRQBTTBPEM6
- DUPLICATE-PROPOSAL EVIDENCE (M002's target): the same demo run created TWO
  checkouts 87 ms apart — chk_01M1E4V6Y5Q0… (from propose_checkout_for_demo,
  baseline-linked, the id the API reports) and chk_01M1E4V6ZTXE… (from
  _pipeline_evaluation's second svc.propose call — the envelope actually
  evaluated by DecisionEngine.decide). Reported checkout ≠ evaluated checkout.
- baseline-linked checkout rows for the intent: 1 (only the FIRST proposal
  captures a baseline; the second has none)
- README: 17,409 B; gallery = plain <img> tags (not clickable) per M004;
  docs section lacks FINAL_README_VIDEO_LOCK_STATUS.md link per M005
- targeted test state: tests/test_semantic_only_demo_f011.py 7/7 (R002 run)
