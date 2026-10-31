#!/usr/bin/env python3
"""Play a sound when CodeBuddy stops and waits for YOU to confirm something.

Why this exists instead of a hook
---------------------------------
CodeBuddy's hooks have a `Notification` event that looks like the right tool,
but it never fires in the IDE: the four entry points that would call the hook
executor (notifyPermissionPrompt / notifyIdle / notifyAuthSuccess /
notifyElicitationDialog) have no callers anywhere in the shipped extension.
See docs/findings.md. So we fall back to watching logs.

What we watch
-------------
JetBrains plugin
    <JetBrainsLogs>/<IDE>/fusion/logs/<hash>/fusion.log
        state_update: running -> waiting_user_input
Desktop IDE
    <CodeBuddyCN>/logs/<ts>/window*/exthost/Tencent-Cloud.coding-copilot/*.log
        needUserConfirm: true

Usage
-----
    python3 lib/watch-confirm.py            run in foreground
    python3 lib/watch-confirm.py --list     list log files we would watch
    python3 lib/watch-confirm.py --once     report recent matches, play nothing
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
BASE = Path(__file__).resolve().parent.parent
NOTIFY = BASE / "bin" / "notify.sh"
MY_LOG = BASE / ".watch.log"
PAUSE_FLAG = BASE / "pause"

# Only accept log files touched within this window, so years of archived
# logs never slow down discovery.
RECENT_SECONDS = 7 * 24 * 3600
POLL_INTERVAL = 0.3
DISCOVER_INTERVAL = 3.0
COOLDOWN = 1.5
MAX_FILES = 40

# (label, root, relative glob, compiled pattern)
# Roots that do not exist on this machine are skipped silently.
import re

SOURCES = [
    (
        "jetbrains-plugin",
        HOME / "Library" / "Logs" / "JetBrains",
        "*/fusion/logs/*/fusion.log",
        re.compile(r"state_update:\s*running\s*\u2192\s*waiting_user_input"),
    ),
    (
        "desktop-ide",
        HOME / "Library" / "Application Support" / "CodeBuddy CN" / "logs",
        "*/window*/exthost/Tencent-Cloud.coding-copilot/*.log",
        re.compile(r"needUserConfirm:\s*true"),
    ),
]


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(MY_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def play() -> None:
    if PAUSE_FLAG.exists():
        return
    try:
        subprocess.Popen(
            ["sh", str(NOTIFY), "--play-confirm"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        log(f"play failed: {exc}")


def discover() -> dict[Path, tuple[str, re.Pattern]]:
    found: dict[Path, tuple[str, re.Pattern]] = {}
    now = time.time()
    for label, root, pattern, regex in SOURCES:
        if not root.is_dir():
            continue
        try:
            candidates = [p for p in root.glob(pattern) if p.is_file()]
        except OSError:
            continue
        fresh = []
        for path in candidates:
            try:
                if now - path.stat().st_mtime <= RECENT_SECONDS:
                    fresh.append(path)
            except OSError:
                continue
        if len(fresh) > MAX_FILES:
            fresh.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            fresh = fresh[:MAX_FILES]
        for path in fresh:
            found[path] = (label, regex)
    return found


class Tailer:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset: int | None = None
        self.inode: int | None = None
        self.buf = b""

    def read_lines(self) -> list[str]:
        try:
            st = self.path.stat()
        except OSError:
            return []
        if self.offset is None:
            self.offset, self.inode = st.st_size, st.st_ino
            return []
        if st.st_ino != self.inode or st.st_size < self.offset:
            self.offset, self.inode, self.buf = 0, st.st_ino, b""
        if st.st_size == self.offset:
            return []
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                chunk = f.read()
                self.offset = f.tell()
        except OSError:
            return []
        parts = (self.buf + chunk).split(b"\n")
        self.buf = parts.pop()
        if len(self.buf) > 4 * 1024 * 1024:
            self.buf = b""
        return [p.decode("utf-8", "replace") for p in parts if p]


def main() -> int:
    if "--list" in sys.argv:
        items = discover()
        if not items:
            print("no log files found on this machine")
        for path, (label, _) in sorted(items.items(), key=lambda kv: kv[1][0]):
            print(f"[{label}] {path}")
        return 0

    if "--once" in sys.argv:
        total = 0
        for path, (label, regex) in discover().items():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            hits = [ln for ln in text.splitlines() if regex.search(ln)]
            if hits:
                total += len(hits)
                print(f"[{label}] {path.name}: {len(hits)} match(es), last: {hits[-1][:120]}")
        print(f"total matches: {total}")
        return 0

    log("watch-confirm started")
    if not any(root.is_dir() for _, root, _, _ in SOURCES):
        log("none of the CodeBuddy log directories exist on this machine; "
            "the watcher will wait for them to appear")

    tailers: dict[Path, Tailer] = {}
    meta: dict[Path, tuple[str, re.Pattern]] = {}
    last_play = 0.0
    last_discover = 0.0

    while True:
        now = time.time()
        if now - last_discover > DISCOVER_INTERVAL:
            last_discover = now
            current = discover()
            for gone in set(tailers) - set(current):
                tailers.pop(gone, None)
                meta.pop(gone, None)
            for path, info in current.items():
                meta[path] = info
                if path not in tailers:
                    tailers[path] = Tailer(path)
                    log(f"watching [{info[0]}] {path}")

        for path, tailer in list(tailers.items()):
            info = meta.get(path)
            if not info:
                continue
            label, regex = info
            for line in tailer.read_lines():
                if not regex.search(line):
                    continue
                if now - last_play < COOLDOWN:
                    continue
                last_play = now
                play()
                log(f"confirm needed [{label}]")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
