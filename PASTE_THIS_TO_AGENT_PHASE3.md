# PASTE THIS TO THE CODING AGENT — PHASE 3

Read `RazorMesh_Trust_Phase3_Master_Prompt.md` completely before modifying anything.

Also read all existing governance files in the precedence defined by `AGENTS.md`.

A local-only secret file named `PHASE3_PRIVATE_BOOTSTRAP_LOCAL_ONLY.md` is present. Before reading its values, ensure that exact file is excluded locally from Git (prefer `.git/info/exclude`) and that root `.env` is ignored. Follow the master prompt to merge the values into `.env` without printing them, update `.env.example` with blank placeholders only, verify TokenRouter safely, then delete the private file after successful authentication.

Follow all 50 milestones exactly ONE AT A TIME:
implement current milestone → validate/tests/security/data/ML gates → required Phase-1/2 regression → inspect real output → update docs/status/memory → local commit only after PASS → next milestone.

Never push.

Stop only at the master prompt's genuine human gates: gold review, Google Colab training, conditional compute if truly necessary, and final Phase-4 approval.

Begin M01 now.
