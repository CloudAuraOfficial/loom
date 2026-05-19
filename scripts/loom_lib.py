"""Loom — workflow framework for Claude Code workspaces.

This module is both a library and a CLI. The bash hooks call it via subcommands;
the slash command (Phase 2) will call it via the same surface.

Subcommands:
  find-root              Print the nearest .loom-owning directory, or empty.
  status                 Print current cycle, stage, and next stages as JSON.
  validate               Validate the current stage's artifact has required H2 sections.
  advance <next_stage>   Advance current-stage if previous artifact validates.
  init <workflow>        Bootstrap .loom/ in the current dir with the named workflow.
  router <tool>          Decision script for PreToolUse hook.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml


LOOM_HOME = Path(os.environ.get("LOOM_HOME", str(Path.home() / "loom")))


# ---------- domain ----------

@dataclass
class Stage:
    id: str
    description: str
    owner_agent: str
    allowed_skills: list[str] = field(default_factory=list)
    blocked_skills: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    blocked_tools: list[str] = field(default_factory=list)
    artifact: str = ""
    artifact_schema: list[str] = field(default_factory=list)
    next: list[str] | None = field(default_factory=list)
    inject_previous: list[str] = field(default_factory=list)
    inject_lessons_from: str = ""


@dataclass
class Workflow:
    name: str
    version: str
    description: str
    stages: list[Stage]
    cycle_artifact_dir: str = "cycles"

    def stage(self, stage_id: str) -> Stage | None:
        return next((s for s in self.stages if s.id == stage_id), None)


# ---------- I/O ----------

def find_loom_root(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / ".loom").is_dir():
            return candidate
    return None


def load_workflow(loom_root: Path) -> Workflow:
    spec_path = loom_root / ".loom" / "workflow.yaml"
    if spec_path.is_symlink():
        spec_path = spec_path.resolve()
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))

    stages: list[Stage] = []
    for s in raw.get("stages", []) or []:
        nxt = s.get("next")
        if nxt is None or nxt == [None]:
            nxt = None
        elif isinstance(nxt, str):
            nxt = [nxt]
        elif isinstance(nxt, list):
            nxt = [x for x in nxt if x is not None] or None
        stages.append(Stage(
            id=s["id"],
            description=s.get("description", ""),
            owner_agent=s["owner_agent"],
            allowed_skills=s.get("allowed_skills") or [],
            blocked_skills=s.get("blocked_skills") or [],
            allowed_tools=s.get("allowed_tools") or [],
            blocked_tools=s.get("blocked_tools") or [],
            artifact=s.get("artifact", ""),
            artifact_schema=s.get("artifact_schema") or [],
            next=nxt,
            inject_previous=s.get("inject_previous") or [],
            inject_lessons_from=s.get("inject_lessons_from", "") or "",
        ))

    return Workflow(
        name=raw["name"],
        version=raw["version"],
        description=raw.get("description", ""),
        stages=stages,
        cycle_artifact_dir=raw.get("cycle_artifact_dir", "cycles"),
    )


def read_current_stage(loom_root: Path) -> str | None:
    f = loom_root / ".loom" / "current-stage"
    if not f.exists():
        return None
    return f.read_text(encoding="utf-8").strip() or None


def write_current_stage(loom_root: Path, stage_id: str) -> None:
    (loom_root / ".loom" / "current-stage").write_text(stage_id, encoding="utf-8")


def current_cycle_dir(loom_root: Path) -> Path:
    cycles_root = loom_root / ".loom" / "cycles"
    current_link = cycles_root / "current"
    if current_link.exists():
        return current_link.resolve()
    cycles_root.mkdir(parents=True, exist_ok=True)
    first = cycles_root / "001"
    (first / "stages").mkdir(parents=True, exist_ok=True)
    if not current_link.exists():
        current_link.symlink_to("001")
    return first


def artifact_path(loom_root: Path, stage: Stage) -> Path:
    return current_cycle_dir(loom_root) / "stages" / stage.artifact


def validate_artifact(path: Path, required_sections: list[str]) -> list[str]:
    if not path.exists():
        return [f"file missing: {path}"]
    text = path.read_text(encoding="utf-8")
    missing = []
    for section in required_sections:
        pat = re.compile(rf"^##\s+{re.escape(section)}\s*$", re.MULTILINE)
        if not pat.search(text):
            missing.append(section)
    return missing


def log_event(loom_root: Path, payload: dict[str, Any]) -> None:
    log_file = loom_root / ".loom" / "loom.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, default=str) + "\n")


def log_only_mode() -> bool:
    return os.environ.get("LOOM_LOG_ONLY", "1") == "1"


# ---------- subcommands ----------

def cmd_find_root(args) -> int:
    root = find_loom_root()
    if root:
        print(root)
    return 0


def cmd_status(args) -> int:
    root = find_loom_root()
    if not root:
        print(json.dumps({"loom": False}))
        return 0
    wf = load_workflow(root)
    cur_id = read_current_stage(root)
    cur_stage = wf.stage(cur_id) if cur_id else None
    cycle_dir = current_cycle_dir(root)
    cycle_id = cycle_dir.name
    state = {
        "loom": True,
        "root": str(root),
        "workflow": wf.name,
        "workflow_version": wf.version,
        "cycle": cycle_id,
        "current_stage": cur_id,
        "current_stage_description": cur_stage.description.strip() if cur_stage else None,
        "owner_agent": cur_stage.owner_agent if cur_stage else None,
        "allowed_skills": cur_stage.allowed_skills if cur_stage else [],
        "blocked_skills": cur_stage.blocked_skills if cur_stage else [],
        "blocked_tools": cur_stage.blocked_tools if cur_stage else [],
        "next_stages": cur_stage.next if cur_stage else [],
        "artifact_path": str(artifact_path(root, cur_stage)) if cur_stage else None,
    }
    print(json.dumps(state, indent=2))
    return 0


def cmd_validate(args) -> int:
    root = find_loom_root()
    if not root:
        print("no .loom directory found", file=sys.stderr)
        return 1
    wf = load_workflow(root)
    stage_id = args.stage or read_current_stage(root)
    if not stage_id:
        print("no current-stage and --stage not provided", file=sys.stderr)
        return 1
    stage = wf.stage(stage_id)
    if not stage:
        print(f"unknown stage {stage_id}", file=sys.stderr)
        return 1
    missing = validate_artifact(artifact_path(root, stage), stage.artifact_schema)
    if missing:
        print(json.dumps({"valid": False, "missing": missing}, indent=2))
        return 2
    print(json.dumps({"valid": True, "stage": stage_id, "artifact": str(artifact_path(root, stage))}, indent=2))
    return 0


def cmd_advance(args) -> int:
    root = find_loom_root()
    if not root:
        print("no .loom directory found", file=sys.stderr)
        return 1
    wf = load_workflow(root)
    cur_id = read_current_stage(root)
    if not cur_id:
        print("no current-stage; run init first", file=sys.stderr)
        return 1
    cur_stage = wf.stage(cur_id)
    if not cur_stage:
        print(f"unknown current-stage {cur_id}", file=sys.stderr)
        return 1

    missing = validate_artifact(artifact_path(root, cur_stage), cur_stage.artifact_schema)
    if missing and not args.force:
        print(json.dumps({
            "advanced": False,
            "reason": "current artifact incomplete",
            "missing_sections": missing,
            "artifact_path": str(artifact_path(root, cur_stage)),
        }, indent=2), file=sys.stderr)
        return 2

    next_id = args.next_stage
    allowed = cur_stage.next or []
    if next_id not in allowed:
        if not allowed:
            print(f"stage {cur_id} is terminal; nothing to advance to", file=sys.stderr)
            return 2
        print(f"{next_id} is not in allowed next stages for {cur_id}: {allowed}", file=sys.stderr)
        return 2

    next_stage = wf.stage(next_id)
    if not next_stage:
        print(f"unknown next stage {next_id}", file=sys.stderr)
        return 1

    write_current_stage(root, next_id)
    log_event(root, {
        "event": "advance",
        "from": cur_id,
        "to": next_id,
        "cycle": current_cycle_dir(root).name,
    })
    print(json.dumps({
        "advanced": True,
        "from": cur_id,
        "to": next_id,
        "next_artifact": str(artifact_path(root, next_stage)),
        "next_owner_agent": next_stage.owner_agent,
    }, indent=2))
    return 0


def cmd_init(args) -> int:
    target = Path.cwd().resolve()
    if (target / ".loom").exists() and not args.force:
        print(".loom already exists; pass --force to reinit", file=sys.stderr)
        return 1

    source_yaml = LOOM_HOME / "workflows" / f"{args.workflow}.yaml"
    if not source_yaml.exists():
        print(f"workflow not found: {source_yaml}", file=sys.stderr)
        return 1

    loom_dir = target / ".loom"
    loom_dir.mkdir(parents=True, exist_ok=True)
    workflow_link = loom_dir / "workflow.yaml"
    if workflow_link.exists() or workflow_link.is_symlink():
        workflow_link.unlink()
    workflow_link.symlink_to(source_yaml)

    wf = load_workflow(target)
    first_stage = wf.stages[0].id if wf.stages else None
    if not first_stage:
        print("workflow has no stages", file=sys.stderr)
        return 1

    write_current_stage(target, first_stage)
    current_cycle_dir(target)  # creates cycle 001/stages/

    (loom_dir / "lessons").mkdir(exist_ok=True)
    index = loom_dir / "cycles" / "current" / "stages" / "INDEX.md"
    index.write_text(
        f"# Cycle {current_cycle_dir(target).name} — {wf.name}\n\n"
        f"Workflow: {wf.name} v{wf.version}\n"
        f"Initial stage: {first_stage}\n\n"
        f"## Transitions\n\n"
        f"- (start)\n",
        encoding="utf-8",
    )
    log_event(target, {"event": "init", "workflow": wf.name, "first_stage": first_stage})

    print(json.dumps({
        "initialized": True,
        "root": str(target),
        "workflow": wf.name,
        "current_stage": first_stage,
        "cycle": "001",
        "artifact_to_produce": str(artifact_path(target, wf.stages[0])),
    }, indent=2))
    return 0


def cmd_router(args) -> int:
    """Cheap decision script for PreToolUse hook."""
    root = find_loom_root()
    if not root:
        print("allow:no-loom")
        return 0
    try:
        wf = load_workflow(root)
    except Exception as exc:
        print(f"allow:load-error:{exc}")
        return 0

    cur_id = read_current_stage(root)
    if not cur_id:
        print("allow:no-stage")
        return 0
    stage = wf.stage(cur_id)
    if not stage:
        print(f"allow:unknown-stage:{cur_id}")
        return 0

    tool = args.tool
    if stage.allowed_tools and tool not in stage.allowed_tools:
        decision = f"block:tool {tool} not in allowed_tools for stage {cur_id}"
    elif tool in stage.blocked_tools:
        decision = f"block:tool {tool} blocked at stage {cur_id}"
    else:
        decision = "allow:ok"

    log_event(root, {
        "event": "router.decision",
        "stage": cur_id,
        "tool": tool,
        "decision": decision,
        "log_only": log_only_mode(),
    })
    print(decision)
    return 0


# ---------- CLI ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="loom", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("find-root").set_defaults(func=cmd_find_root)
    sub.add_parser("status").set_defaults(func=cmd_status)

    v = sub.add_parser("validate")
    v.add_argument("--stage")
    v.set_defaults(func=cmd_validate)

    a = sub.add_parser("advance")
    a.add_argument("next_stage")
    a.add_argument("--force", action="store_true")
    a.set_defaults(func=cmd_advance)

    i = sub.add_parser("init")
    i.add_argument("workflow")
    i.add_argument("--force", action="store_true")
    i.set_defaults(func=cmd_init)

    r = sub.add_parser("router")
    r.add_argument("tool")
    r.set_defaults(func=cmd_router)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
