# OpenClaw Runtime/Protocol Analysis (2026-02-20)

## 1) Tool protocol model (observed)

OpenClaw agent turns produce tool calls as structured RPC payloads (tool name + validated args), then continue with tool results.
Core behavior from docs/source:

- Tool surface is policy-filtered (`tools.profile`, `tools.allow`, `tools.deny`)
- Some tools are grouped (`group:web`, `group:automation`, etc.)
- Session routing distinguishes main vs isolated runs (`cron` payload/sessionTarget rules)
- Subagents run in isolated session trees with visibility controls

## 2) Permission/control layers (stacked)

1. Tool policy (global/per-agent/per-provider)
2. Elevated mode gating (`/elevated`, sender allowlists)
3. Exec security mode (`deny|allowlist|full`)
4. Exec approvals (`ask` policy, allowlist, approval lifecycle)
5. Channel authorization/command allowlists

Net effect: tool execution is allowed only if *all* relevant layers agree.

## 3) Continuity model (when action continues vs stops)

Action continues when:
- User turn requests work and no blocking approval is needed
- Background worker (subagent/cron/exec) remains active
- Heartbeat/cron wakes session for follow-up

Action stops when:
- Turn completes without queued background tasks
- Approval timeout/denial occurs
- Tool policy denies required action
- Background run exits/fails without recovery path

## 4) Known friction points

- Multi-step autonomy is fragmented across: main turn, subagent runs, cron wakeups
- Approval-gated flows can stall without explicit resume policy
- No single explicit state machine for "goal-level persistence" visible to users
- Context drift across long chains unless explicit artifact/checkpoint strategy exists

## 5) Proposed "better-than-current" architecture

## A. Goal Runtime Layer (GRL)
A deterministic supervisor loop above normal turns:

- Goal object:
  - id, objective, success criteria, deadline, risk level
  - plan graph (tasks), state, blockers, evidence links
- Tick loop:
  1. ingest new events/messages
  2. re-evaluate blockers/risk
  3. schedule next best action
  4. execute via policy-aware action router
  5. checkpoint + user-visible delta report

## B. Explicit Action State Machine
`PLANNED -> READY -> NEEDS_APPROVAL -> RUNNING -> VERIFYING -> DONE | BLOCKED | ABORTED`

Benefits:
- Users see why it stopped
- Resume token + reason attached to each blocked step
- Better automation for retries/escalation

## C. Policy-Aware Planner (PAP)
Planner reasons with permission envelopes before proposing actions:

- If action requires unavailable permission, planner outputs
  - alternative path, or
  - approval request package with minimal scope

## D. Artifact-First Continuity
All long tasks must emit structured artifacts:
- `artifacts/<goal-id>/plan.json`
- `artifacts/<goal-id>/runs/*.json`
- `artifacts/<goal-id>/status.md`

This reduces reliance on volatile context windows.

## E. Deadline-oriented execution
For requests like "by 10:00":
- auto-schedule staged checkpoints (T-120, T-60, T-15, T)
- each checkpoint has required deliverable contract
- miss triggers fallback summary and blockers report automatically

## 6) Minimal implementation plan

Phase 1 (local prototype):
- Goal schema + state machine + router simulation
- Checkpoint scheduler
- Telegram-ready delta summary renderer

Phase 2 (integration):
- Wrap subagent/cron as executor backends
- Attach approval lifecycle hooks

Phase 3 (hardening):
- Retry budget, idempotency keys, policy proofs, audit export

