# RazorMesh — Video Recording Checklist (one screen)

**Do immediately before pressing Record. Full details: `docs/submission/VIDEO_RECORDING_MASTER_SCRIPT.md` (§19).**

## Systems

- [ ] Docker/Postgres/Redis running (`docker compose ps` → both healthy)
- [ ] API health + ready OK (http://127.0.0.1:8000/ready → `status: ok`)
- [ ] Frontend loaded (http://localhost:3000 → 200)
- [ ] Razorpay TEST badge visible (preflight: RAZORPAY TEST MODE)
- [ ] TokenRouter compiler reachable — **run one test compile** (60 s budget; if 502, wait 10 min, retry ×3, else record the EMERGENCY SHORT cut)
- [ ] Semantic model loaded (preflight: phase3-finetuned-v2 · semantic-thresholds-v3)
- [ ] Challenger status known (optional — shadow beat skippable; static table still works)
- [ ] Preflight + warm-up compiler run → **REQUIRED SYSTEMS READY**

## Recording setup

- [ ] Resolution 1920×1080 · Chrome zoom 100%
- [ ] Mission Control in **Presenter mode** (RECORDING VIEW badge)
- [ ] No devtools · bookmarks bar hidden · terminal windows hidden
- [ ] No secrets visible (no `.env`, no keys, no `/reviewer`)
- [ ] Do-Not-Disturb ON · mic checked

## Tab order (fixed — Cmd+N is stable)

1. Mission Control `/mission-control` (pre+warm preflight open)
2. Buyer `/buyer`
3. Security Lab `/security-lab` (scrolled to Why-semantic-AI card)
4. Governance `/governance` (metrics table in view)
5. Audit `/audit`

## Main story (3:30–4:00)

1. TAB 1: problem + pipeline sweep (00:00–00:20)
2. TAB 2: paste mandate → **Compile mandate** (narrate the wait) → **Confirm — grant authority** → agent search → pick **#3 Sony WH-1000XM5** → **Propose checkout** → ALLOW
3. TAB 1: **Hidden recurring on current** → diff (recurring No→Yes) → **Execute current transaction** → **STALE_CHECKOUT** → Provider calls 0
4. TAB 5: trace card → timeline → **▶ Play** (read-only) → **Verify hash chain**
5. TAB 3: **Run WHY SEMANTIC AI MATTERS demo** → ALLOW / BLOCK / BLOCK / **NOT ISSUED** / **NOT CREATED** / 0
6. TAB 4: REJECTED challenger table (2→7, 0.893→0.7757, 5→6, 0.7367→0.9752) → optional **Run shadow check**
7. TAB 1: closing shot on the pipeline

## Final line (say exactly)

> "RazorMesh lets AI agents propose and negotiate — without ever giving them
> authority to spend. The AI proposes. RazorGuard authorizes. The trusted
> executor executes. The transaction that executes must still be the
> transaction the human authorized. That is intent-to-execution integrity."

**Never say:** "payment completed" (Test order created exactly once) · "all five
protocols use signatures" (UCP+AP2 crypto; MCP/ACP/A2A binding evidence) ·
"v2 active" (PRE_V2 active; v2 shadow-only) · any invented metric ·
milestone codes. **If a live step fails:** follow §17 — retry once, then fall
back honestly; never fake a state.
