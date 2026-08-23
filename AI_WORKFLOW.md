# AI_WORKFLOW.md — Autonomous Milestone Protocol

## 1. Session start

Before coding:

```text
inspect repo
  ↓
git status
  ↓
read governance docs
  ↓
read current status/memory
  ↓
identify next milestone
  ↓
verify previous gate
```

Do not edit first and understand later.

---

# 2. Milestone preflight checklist

For milestone N:

- [ ] Read milestone definition.
- [ ] Identify PRD requirement IDs involved.
- [ ] Identify security invariants involved.
- [ ] Inspect current implementation.
- [ ] Inspect relevant accepted decisions.
- [ ] Confirm version/dependency assumptions.
- [ ] Define acceptance tests before or alongside implementation.
- [ ] Confirm no external credential is required in Phase 1.

---

# 3. Implementation loop

```text
PLAN
 ↓
IMPLEMENT SMALLEST CORRECT CHANGE
 ↓
FORMAT
 ↓
LINT
 ↓
TYPECHECK
 ↓
UNIT TEST
 ↓
INTEGRATION TEST
 ↓
SECURITY REGRESSION
 ↓
PROPERTY/CONCURRENCY TEST IF RELEVANT
 ↓
FULL RELEVANT REGRESSION
 ↓
INSPECT OUTPUT
```

If failure:

```text
read exact error
 ↓
find root cause
 ↓
targeted fix
 ↓
rerun narrow failure
 ↓
rerun subsystem
 ↓
rerun regression
```

Maximum 5 serious attempts for the same unresolved root cause before blocker report.

---

# 4. Milestone evidence

For each milestone `PHASE1_STATUS.md` must record:

- implementation summary;
- files changed;
- exact validation commands;
- pass/fail;
- security regression performed;
- known limitations;
- decision IDs created;
- next milestone.

Do not record PASS from assumptions.

---

# 5. Documentation sync before next milestone

Always update:

- `PHASE1_STATUS.md`;
- `MEMORY.md`.

Conditionally update:

- `DECISIONS.md`;
- `ARCHITECTURE.md`;
- `SECURITY.md`;
- `DESIGN.md`;
- `VERSION_MANIFEST.md`;
- `RESEARCH.md`;
- `TESTING.md`.

Then re-read changed documents to verify they agree with code.

---

# 6. Memory compaction

`MEMORY.md` is a current-state summary.

After each milestone:

- set current/next milestone;
- add newly proven state;
- remove stale operational noise;
- keep blockers;
- keep relevant human-owned inputs;
- link decision IDs;
- never turn it into a transcript.

---

# 7. Decision recording

Create a new decision entry when:

- a significant design choice is made;
- a dependency choice affects architecture/security;
- a requirement is interpreted in a non-obvious way;
- a prior decision is superseded.

Do not create decision spam for trivial variable/file naming.

---

# 8. Research workflow

When external current information is needed:

1. search authoritative sources;
2. prefer official sources;
3. record finding in `RESEARCH.md`;
4. distinguish fact vs interpretation;
5. update `VERSION_MANIFEST.md` or relevant source-of-truth file;
6. cite source in decision rationale when it changed architecture.

---

# 9. Human gate output

When human action is genuinely required, stop and output:

```text
HUMAN GATE

Milestone:
Blocked action:
Why autonomous continuation is unsafe/impossible:
Exact human steps:
Official website/source:
How the human verifies success:
What the agent will do immediately after:
```

Do not continue unrelated milestone work while the core milestone is blocked.

---

# 10. Phase gate

After M50:

- run clean-room acceptance;
- create completion report;
- update all governance docs;
- stop;
- request human approval before Phase 2.

Do not start real Razorpay integration automatically.
