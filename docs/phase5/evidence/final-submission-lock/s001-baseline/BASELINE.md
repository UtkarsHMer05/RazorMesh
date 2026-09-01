# S001 — Submission baseline (frozen before S002-S010)

- start HEAD: 6b5240d6ea66dccf2455c8986faffc08918805e8 (Final Video Truth Fix F001-F015)
- git status: clean (0 modified)
- Active semantic runtime: deberta / phase3-finetuned-v2 / semantic-thresholds-v3 (PRE_V2)
- Challenger: AgentPay-IR v2 (A_2ep) — NOT activated, shadow-only, artifact available
- Semantic-only demo (F011 state): honest=true, runtime phase3-finetuned-v2;
  deterministic lane via local structured-facts helper (S002 will replace with
  the REAL RazorGuard machinery)
- Preflight (S003 input state): 8 probes all ready; AI Intent Compiler reported
  as "configured" without live reachability distinction; "Protocol keys" label;
  no required/optional split; payment env RAZORPAY TEST MODE (no
  validate_payment_provider_config call)
- Audit chain: valid over 2,536 events (dev DB)
- README: 150-line text-heavy technical README (S006 will rework)
- Test counts at baseline: backend 992 collected (main 789 passed last run;
  phase4 203/203; live-ingress 13/13 isolation; vitest 35/35; playwright 46
  passed + 3 reviewer env-gated + 1 order flake)
- 8 GitHub-facing page captures: landing/buyer/mission-control/merchant/
  protocols/security-lab/audit/governance (.png in this dir)
