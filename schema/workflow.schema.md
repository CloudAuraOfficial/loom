# Workflow YAML schema

A workflow is declared in a single YAML file in `workflows/<name>.yaml`. Projects reference it from their `.loom/workflow.yaml` (usually a symlink).

## Top-level fields

| Field | Required | Type | Purpose |
|---|---|---|---|
| `name` | yes | string | Unique workflow identifier (kebab-case). Becomes the value of `.loom/workflow-name`. |
| `version` | yes | string | Semver. Bumped on schema-incompatible changes; projects can pin a version. |
| `description` | yes | string | One-line summary. Shown in `/loom-status`. |
| `stages` | yes | list | Ordered list of stage objects (see below). First stage is the entry point. |
| `cycle_artifact_dir` | no | string | Default: `cycles`. Per-cycle artifacts go to `.loom/cycles/NNN/stages/`. |

## Stage fields

| Field | Required | Type | Purpose |
|---|---|---|---|
| `id` | yes | string | Kebab-case stage identifier. Unique within a workflow. |
| `description` | yes | string | What this stage produces. Shown in `/loom-status` and injected into the owner agent's prompt. |
| `owner_agent` | yes | string | Agent name (matches a file in `~/rogerclaude/agents/<name>.md`). The agent invoked by `/loom-advance`. |
| `allowed_skills` | no | list[string] | Skills explicitly enabled for this stage. Other skills are still callable unless `blocked_skills` lists them. |
| `blocked_skills` | no | list[string] | Skills the Context Router blocks during this stage. |
| `allowed_tools` | no | list[string] | Whitelist for built-in tools (Edit, Write, Bash, etc.). If present, only listed tools are allowed. |
| `blocked_tools` | no | list[string] | Blocklist for built-in tools. Cannot coexist with `allowed_tools`. |
| `artifact` | yes | string | Filename for the stage's output, relative to the cycle's `stages/` dir. Convention: `NN-<id>.md`. |
| `artifact_schema` | yes | list[string] | Required H2 sections in the artifact. Loom enforces presence (not content quality) at advance time. |
| `next` | yes | list[string] OR null | Allowed next stage ids. `null` means terminal stage. Multiple values enable branching/cycles. |
| `inject_previous` | no | list[string] | Which previous artifacts (by stage id) to inject into the owner's prompt. Default: just the immediately preceding artifact. |
| `inject_lessons_from` | no | string | Stage id to gather `Lessons for future cycles` sections from across past cycles. Useful for self-improving stages. |

## Artifact contract

Every artifact must be a markdown file containing:

1. A YAML frontmatter block with `stage`, `cycle`, `owner_agent`, `started_at`, `completed_at`, `next_stage` (or `terminal: true`).
2. An H2 section for **each** item in `artifact_schema`.
3. A `## Lessons for future cycles` section, even if empty. This is what `inject_lessons_from` reads.

If any required section is missing at advance time, the hook blocks the next `/loom-advance` until it's filled in.

## Cycles

A cycle is one pass through the workflow. `.loom/cycles/NNN/` (zero-padded 3 digits initially, expandable) holds one cycle's artifacts.

`.loom/cycles/current` is a symlink to the active cycle directory. `loom-advance` advances within a cycle; reaching a `next: null` stage closes the cycle and `/loom-init-cycle` opens a new one.

## Lessons accumulation

Across cycles, the same stage's `Lessons for future cycles` sections accumulate at `.loom/lessons/<stage-id>.md`. When `inject_lessons_from` is set, the hook injects this aggregated file (truncated to N most recent entries if too large).

## Worked example

See `workflows/video-studio.yaml` and `examples/tanmatra-studio.loom/`.
