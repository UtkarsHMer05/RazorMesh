# RazorMesh Trust — Governance Pack

This pack is intended to be copied into the repository root **before the coding agent continues Phase 1**.

## Install order

1. Back up or commit any existing work you care about.
2. Copy these Markdown files into the RazorMesh repository root.
3. If a file with the same name already exists, **do not blindly overwrite it**. Ask the coding agent to compare and merge it while preserving user-authored requirements and previous accepted decisions.
4. Paste the contents of `PASTE_THIS_TO_AGENT.md` into the coding agent.
5. The agent must read the governance files before modifying implementation code.

## Core source-of-truth files

| File | Purpose |
|---|---|
| `AGENTS.md` | Master operating contract for any coding agent |
| `RULES.md` | Non-negotiable engineering/security rules |
| `PRD.md` | Product requirements and Phase-1 acceptance criteria |
| `PHASES.md` | Project phase boundaries and future roadmap |
| `ARCHITECTURE.md` | Application flow, modules, data authority, folder structure, tech stack |
| `SECURITY.md` | Threat model, security invariants and defensive scenarios |
| `DESIGN.md` | UI/UX and Razorpay/RazorSense-inspired design requirements |
| `DECISIONS.md` | Append-only architectural/product decision record |
| `MILESTONES.md` | The gated 50-milestone Phase-1 execution plan |
| `TESTING.md` | Required test gates, benchmark definitions and release criteria |
| `VERSION_MANIFEST.md` | Live-resolved dependency/runtime versions and evidence |
| `RESEARCH.md` | Research evidence, official-source log and open questions |
| `PHASE1_STATUS.md` | Milestone-by-milestone execution status and evidence |
| `MEMORY.md` | Compact rolling handoff/current-state memory |
| `AI_WORKFLOW.md` | Exact autonomous milestone loop and documentation sync rules |
| `PASTE_THIS_TO_AGENT.md` | Prompt to paste into the coding agent after installing this pack |

## Authority model

The status/memory files are **not requirements**. They can report what happened, but they cannot silently redefine product scope or security.

When requirements conflict, follow the precedence documented in `AGENTS.md`.

## Important

Phase 1 remains credential-free and local. It must not require Razorpay, OpenAI, Anthropic, Gemini, Modal, Colab, or other external credentials.

The Phase-1 objective is to build and prove the local trust core first.
