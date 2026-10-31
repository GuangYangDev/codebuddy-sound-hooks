#!/usr/bin/env python3
"""Merge codebuddy-sound-hooks into CodeBuddy's settings.json.

Why a separate script: users almost always already have hooks configured.
Overwriting settings.json would silently destroy their setup, so every
operation here is additive and idempotent.

Commands:
    add <path-to-notify.sh>   add Stop + Notification hooks (safe to re-run)
    remove                    remove only our own entries
    status                    show what we currently have configured
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

# Any hook entry whose command mentions this string is considered ours.
# Deliberately distinctive: a generic "notify.sh" would also match unrelated
# scripts that happen to share the name.
MARKER = "codebuddy-sound-hooks"

EVENTS = ("Stop", "Notification")

BACKUP_SUFFIX = ".bak.codebuddy-sound-hooks"


def settings_path() -> Path:
    return Path.home() / ".codebuddy" / "settings.json"


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"refusing to touch a malformed settings.json: {exc}")
    if not isinstance(data, dict):
        sys.exit("refusing to touch settings.json: unexpected top-level type")
    return data


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, str(path) + BACKUP_SUFFIX)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def our_commands(event_entries: list) -> list[str]:
    found = []
    for entry in event_entries:
        if not isinstance(entry, dict):
            continue
        for hook in entry.get("hooks", []):
            if isinstance(hook, dict) and MARKER in hook.get("command", ""):
                found.append(hook["command"])
    return found


def cmd_add(notify_path: str) -> int:
    path = settings_path()
    data = load(path)
    hooks = data.setdefault("hooks", {})
    # The trailing comment doubles as a stable marker for later removal.
    command = f'sh "{notify_path}" # {MARKER}'

    changed = []
    for event in EVENTS:
        entries = hooks.setdefault(event, [])
        if not isinstance(entries, list):
            sys.exit(f"refusing to touch settings.json: hooks.{event} is not a list")
        if our_commands(entries):
            continue
        entries.append({"hooks": [{"type": "command", "command": command}]})
        changed.append(event)

    if changed:
        save(path, data)
        print(f"hooks added: {', '.join(changed)}")
        print(f"backup   : {path}{BACKUP_SUFFIX}")
        print("Changes take effect immediately — no IDE restart needed.")
    else:
        print("hooks already present, nothing to do")

    print(f"settings : {path}")
    return 0


def cmd_remove() -> int:
    path = settings_path()
    if not path.exists():
        print("no settings.json, nothing to remove")
        return 0

    data = load(path)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        print("no hooks configured, nothing to remove")
        return 0

    changed = []
    for event in list(hooks.keys()):
        entries = hooks.get(event)
        if not isinstance(entries, list):
            continue
        kept = []
        for entry in entries:
            if not isinstance(entry, dict):
                kept.append(entry)
                continue
            inner = entry.get("hooks")
            if not isinstance(inner, list):
                kept.append(entry)
                continue
            rest = [h for h in inner if not (isinstance(h, dict) and MARKER in h.get("command", ""))]
            if len(rest) == len(inner):
                kept.append(entry)
            elif rest:
                # Entry had other hooks too; keep them, drop only ours.
                kept.append({**entry, "hooks": rest})
            else:
                changed.append(event)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)

    if changed:
        if not hooks:
            data.pop("hooks", None)
        save(path, data)
        print(f"hooks removed: {', '.join(changed)}")
    else:
        print("no codebuddy-sound-hooks entries found")
    return 0


def cmd_status() -> int:
    path = settings_path()
    data = load(path)
    hooks = data.get("hooks") or {}
    found = False
    for event in EVENTS:
        entries = hooks.get(event)
        if not isinstance(entries, list):
            continue
        ours = our_commands(entries)
        if ours:
            found = True
            print(f"{event}: {ours[0]}")
    if not found:
        print("not installed")
    print(f"settings: {path}")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    action = sys.argv[1]
    if action == "add":
        if len(sys.argv) < 3:
            sys.exit("usage: settings.py add <path-to-notify.sh>")
        return cmd_add(sys.argv[2])
    if action == "remove":
        return cmd_remove()
    if action == "status":
        return cmd_status()
    sys.exit(f"unknown action: {action}")


if __name__ == "__main__":
    sys.exit(main())
