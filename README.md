# Loom

A thin workflow framework for Claude Code workspaces. Turns descriptive CLAUDE.md tool-selection guidance into **enforced** stage gates with auto-generated documentation between stages.

## What problem does this solve?

When a project has many tools, skills, and subagents, two things go wrong:
1. **Tool noise** — every task sees every tool, the model wastes context on irrelevant capabilities (the "MCP/Tools Tax").
2. **Context spelunking** — future sessions read the codebase to understand decisions that were made in a previous session.

Loom addresses both by encoding the workflow as a YAML spec and using Claude Code hooks to:
- Gate which skills/tools are available based on the current stage (the "Context Router").
- Require each stage to produce a markdown artifact before the next stage starts.
- Inject the previous artifact into context when the next stage begins.

## How it composes with what you have

Loom does **not** replace agents, skills, or MCP servers. It orchestrates them:

```
your existing agents (architect, strategist, devops, …)
    +
your existing skills (research-agg, content-engine, frontend-design, …)
    +
your existing hooks (claude-mem, session-gap-check, …)
    +
Loom (governs which subset is active per stage)
```

## Core concepts

- **Workflow** — YAML file declaring a sequence of stages, who owns each, which skills/tools are allowed, and what artifact each must produce.
- **Stage** — one step in a workflow. Has an owner agent, allowed/blocked skills, an artifact schema.
- **Artifact** — markdown file produced by a stage. Becomes context for downstream stages.
- **Cycle** — one full pass through the workflow. Tanmatra produces one cycle per video (~1/day per channel).
- **Context Router** — PreToolUse hook that blocks tools/skills the current stage shouldn't use.

## Repo layout

```
loom/
├── schema/                  # workflow.yaml + artifact format specs
├── workflows/               # workflow library (one .yaml per workflow type)
├── hooks/                   # the 3 Claude Code hook scripts
├── scripts/                 # loom-init, loom-advance, loom-status, loom-back, loom_lib.py
├── examples/                # reference .loom/ directories
└── docs/                    # CONCEPTS.md, USAGE.md, design notes
```

## Status

**Phase 1 — MVP.** First user: Tanmatra Studio (`video-studio.yaml`). Hooks run in `LOOM_LOG_ONLY=1` mode by default during validation; flip to enforcing only after the workflow proves useful.

## Design principles

1. **Compose, don't replace.** Loom uses Claude Code's native primitives (hooks, subagents, skills, slash commands). No external orchestrator service.
2. **Docs are the artifact.** Every stage's output is markdown read by the next stage. Code lives in code; decisions live in docs.
3. **Enforce, don't suggest.** CLAUDE.md decision trees are descriptive. Loom hooks enforce.
4. **Cycles, not lines.** Workflows are graphs with feedback loops, not one-shot pipelines. Each cycle reads lessons from prior cycles.
5. **Opt-in per project.** A project has Loom only if it has a `.loom/` directory. No project, no overhead.
