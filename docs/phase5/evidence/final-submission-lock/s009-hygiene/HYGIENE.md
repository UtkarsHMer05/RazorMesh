S009 HYGIENE SCAN — final record
================================
date: 2026-09-01
- .env: gitignored, untracked (verified exit=1 on git grep for both the real Razorpay Test key id and the real TokenRouter key across ALL tracked files)
- infra/keys/: gitignored, untracked
- AI-workflow/internal files: AGENTS.md + both master-prompt .md files are gitignored and untracked; no paste-this/prompt files tracked
- tracked governance docs (RULES.md, MEMORY.md, DECISIONS.md): project governance only, zero private review text
- review/corpus data: committed synthetic corpus + review packs (product-listing text) by design; NO decisions_working, NO role manifests, NO review-linkage files, NO human-gold row text tracked
- card data: only the standard Razorpay TEST card 4111 1111 1111 1111 in documented test instructions / synthetic scenario fixtures — no real card data
- secret-shaped literals: all allowlisted synthetic fixtures with justifications (scripts/security_check.py allowlist + TESTING.md); the scan itself is a release gate — PASS 0 blocking
- screenshots: captured by script from the real app; content-verified via rendered-DOM assertions (no devtools, no unrelated tabs, no secrets, no card data)

RESULT: PUBLIC-REPOSITORY-SAFE
