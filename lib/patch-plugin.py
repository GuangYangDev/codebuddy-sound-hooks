#!/usr/bin/env python3
"""Let the log watcher see subagent confirmations.

Why this exists
---------------
The "waiting for you" sound is driven by lines CodeBuddy writes into its own
log. For the main agent that works: before showing a permission prompt the
plugin prints

    [ToolListener][PERM-DIAG] onUserConfirmRequired called: ...
    [AcpSessionEventHandler] state_update: running→waiting_user_input

A subagent is a different code path. Its tools answer to
`SubagentToolListener.onUserConfirmRequired`, which reports through
`this.logger.info(...)`. `LoggerImpl.info` writes with `console.info`, and the
IDE's extension host does not forward `console.info` into `fusion.log` — check
it yourself: `[AgentSessionManager]`, `[DispatchContextManager]` and
`[SubagentToolListener]` appear in the bundle and never in the log. So a
subagent can sit there waiting for approval with nothing to watch.

This script flips that single call site from `this.logger.info` to
`console.log`. `console.log` does reach `fusion.log`, and
`lib/watch-confirm.py` already knows the sentence to look for. Nothing else in
the bundle is touched.

Commands
--------
    python3 lib/patch-plugin.py --status    report patched / unpatched / unsupported
    python3 lib/patch-plugin.py --apply     patch every install found (idempotent)
    python3 lib/patch-plugin.py --revert    restore the bytes we backed up
    python3 lib/patch-plugin.py --file PATH work on one bundle only (other IDEs)

`--revert` refuses when the bundle on disk is not the patched one, because that
means a CodeBuddy update replaced it and the backup belongs to an older version.
`--revert --force` restores anyway.

Trade-offs, stated plainly
--------------------------
* It edits a file owned by the plugin. A CodeBuddy update replaces that file,
  and the sound for subagent confirmations silently stops until you re-run
  `--apply`. `--status` is the way to notice.
* The IDE has to be restarted; the extension host loads the bundle at startup.
* `--revert` puts the original bytes back from the backup written on first
  apply, so nothing is lost.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Both sides are one line of minified JS. The anchor is unique in every
# version shipped so far; if it stops being unique we refuse to guess.
FROM = "this.logger.info(`[SubagentToolListener] User confirmation required"
TO = "console.log(`[SubagentToolListener] User confirmation required"

BACKUP_SUFFIX = ".codebuddy-sound-hooks.orig"

BUNDLE_TAIL = Path(
    "plugins/coding-copilot-jetbrains/vsix/extension/out/extension/index.js"
)


def candidate_roots() -> list[Path]:
    home = Path.home()
    return [
        home / "Library" / "Application Support" / "JetBrains",  # macOS
        home / ".local" / "share" / "JetBrains",  # Linux
        home / "AppData" / "Roaming" / "JetBrains",  # Windows
    ]


def find_bundles() -> list[Path]:
    found: list[Path] = []
    for root in candidate_roots():
        if not root.is_dir():
            continue
        for ide_dir in sorted(root.iterdir()):
            bundle = ide_dir / BUNDLE_TAIL
            if bundle.is_file():
                found.append(bundle)
    return found


def read(bundle: Path) -> str:
    return bundle.read_text(encoding="utf-8", errors="surrogateescape")


def classify(text: str) -> str:
    patched = text.count(TO)
    unpatched = text.count(FROM)
    if patched == 1 and unpatched == 0:
        return "patched"
    if unpatched == 1 and patched == 0:
        return "patchable"
    return "unsupported"


def node_available() -> bool:
    return shutil.which("node") is not None


def syntax_ok(path: Path) -> bool:
    try:
        return subprocess.run(
            ["node", "--check", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
    except OSError:
        return True


def safe_to_write(bundle: Path, new_text: str) -> bool:
    """Parse the patched bundle before publishing it, when node is around."""
    if not node_available():
        return True
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8", errors="surrogateescape") as tmp:
        tmp.write(new_text)
        tmp_path = Path(tmp.name)
    try:
        if not syntax_ok(tmp_path):
            # If the original does not parse either, we cannot tell our change
            # apart from a bundler quirk; skip the check instead of blocking.
            return not syntax_ok(bundle)
        return True
    finally:
        tmp_path.unlink(missing_ok=True)


def cmd_status(bundles: list[Path]) -> int:
    if not bundles:
        print("no CodeBuddy JetBrains plugin found on this machine")
        return 1
    for bundle in bundles:
        print(f"{classify(read(bundle)):<12} {bundle}")
    return 0


def cmd_apply(bundles: list[Path], dry_run: bool) -> int:
    if not bundles:
        print("no CodeBuddy JetBrains plugin found on this machine")
        return 1
    changed = 0
    for bundle in bundles:
        text = read(bundle)
        state = classify(text)
        if state == "patched":
            print(f"already patched  {bundle}")
            continue
        if state == "unsupported":
            print(f"unsupported      {bundle}")
            print("    the plugin changed; this project has no anchor for this version")
            continue

        new_text = text.replace(FROM, TO, 1)
        if not safe_to_write(bundle, new_text):
            print(f"refused          {bundle}")
            print("    patched bundle failed `node --check`, nothing written")
            continue
        if dry_run:
            print(f"would patch      {bundle}")
            continue

        # Always refresh: after a CodeBuddy update the leftover backup belongs
        # to the previous version, and restoring it would roll the plugin back.
        backup = Path(str(bundle) + BACKUP_SUFFIX)
        shutil.copy2(bundle, backup)
        tmp = Path(str(bundle) + ".tmp")
        tmp.write_text(new_text, encoding="utf-8", errors="surrogateescape")
        os.replace(tmp, bundle)
        print(f"patched          {bundle}")
        print(f"    backup       {backup}")
        changed += 1

    if changed:
        print()
        print("Restart the IDE (or switch it off and on) so the plugin reloads.")
        print("Then a subagent that asks for confirmation plays the Ping sound.")
    return 0


def cmd_revert(bundles: list[Path], force: bool) -> int:
    if not bundles:
        print("no CodeBuddy JetBrains plugin found on this machine")
        return 1
    restored = 0
    for bundle in bundles:
        backup = Path(str(bundle) + BACKUP_SUFFIX)
        state = classify(read(bundle))
        if not backup.exists():
            print(f"{state:<16} {bundle} (no backup to restore)")
            continue
        if state != "patched" and not force:
            # The bundle is not our patched copy, so the backup predates a
            # plugin update. Restoring it would downgrade the plugin.
            print(f"skipped          {bundle}")
            print("    bundle is not patched (a CodeBuddy update replaced it)")
            print(f"    backup kept at {backup}; --revert --force restores it anyway")
            continue
        os.replace(backup, bundle)
        print(f"reverted         {bundle}")
        restored += 1
    if restored:
        print()
        print("Restart the IDE so the plugin reloads the original bundle.")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args or any(arg in ("-h", "--help") for arg in args):
        sys.exit(__doc__)

    action = next((a for a in args if a in ("--status", "--apply", "--revert")), None)
    if action is None:
        sys.exit(f"unknown action: {' '.join(args)}")

    dry_run = "--dry-run" in args
    bundles: list[Path] = []
    if "--file" in args:
        index = args.index("--file")
        if index + 1 >= len(args):
            sys.exit("--file needs a path to the plugin's index.js")
        target = Path(args[index + 1]).expanduser()
        if not target.is_file():
            sys.exit(f"not a file: {target}")
        bundles = [target]
    else:
        bundles = find_bundles()

    if action == "--status":
        return cmd_status(bundles)
    if action == "--apply":
        return cmd_apply(bundles, dry_run)
    return cmd_revert(bundles, force="--force" in args)


if __name__ == "__main__":
    sys.exit(main())
