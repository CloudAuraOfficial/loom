# Using Loom in a project

## Bootstrap a project

```bash
cd my-project
python3 ~/loom/scripts/loom_lib.py init video-studio
```

This creates `.loom/` in the current directory with the workflow, sets `current-stage` to the first stage, and opens cycle 001.

## Inspect state

```bash
python3 ~/loom/scripts/loom_lib.py status      # JSON dump of current state
python3 ~/loom/scripts/loom_lib.py validate    # check current artifact has required sections
```

## Work the current stage

1. Read the artifact path from `status` (e.g. `.loom/cycles/001/stages/01-research.md`).
2. Invoke the stage's owner agent. The agent's job is to fill that file with content matching the stage's `artifact_schema`.
3. Each artifact needs:
   - YAML frontmatter (`stage`, `cycle`, `owner_agent`, `started_at`, `completed_at`, `next_stage`).
   - One `## <Section>` for each item in `artifact_schema`.
   - A `## Lessons for future cycles` section (always present, can be empty for first cycle).

## Advance to the next stage

```bash
python3 ~/loom/scripts/loom_lib.py advance define
```

`advance` validates the current artifact first. If sections are missing, it refuses unless you pass `--force`.

## Wire the hooks into Claude Code (Phase 2)

Add to `~/.claude/settings.json` — keeping log-only mode until you trust the gating:

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "", "hooks": [
          { "type": "command", "command": "~/loom/hooks/pre-tool-use.sh", "timeout": 5 }
      ]}
    ],
    "SessionStart": [
      { "matcher": "", "hooks": [
          { "type": "command", "command": "~/loom/hooks/session-start.sh", "timeout": 5 }
      ]}
    ]
  }
}
```

Env vars:

| Var | Default | Effect |
|---|---|---|
| `LOOM_LOG_ONLY` | `1` | Log decisions instead of enforcing. Use until comfortable. |
| `LOOM_BYPASS` | `0` | Skip Loom entirely for this command/session. |
| `LOOM_HOME` | `~/loom` | Where the framework lives. |

## When NOT to use Loom

For one-shot tasks (typo fixes, ad-hoc questions, exploratory commands), Loom is overhead. Just don't run `loom init` in those projects. Without `.loom/`, the hooks pass through silently.
