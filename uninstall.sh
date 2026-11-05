#!/bin/bash
# codebuddy-sound-hooks uninstaller
#
# Removes only what this project added. Your other hooks and all other
# settings.json content are left untouched.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.codebuddy-sound-hooks.watch-confirm.plist"
LABEL="com.codebuddy-sound-hooks.watch-confirm"

echo "==> removing confirmation watcher"
if launchctl print "gui/$(id -u)/${LABEL}" >/dev/null 2>&1; then
    launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
    echo "    stopped $LABEL"
else
    echo "    not running"
fi
rm -f "$PLIST"

echo "==> removing CodeBuddy hooks"
python3 "$REPO_DIR/lib/settings.py" remove

echo "==> restoring the CodeBuddy plugin bundle"
python3 "$REPO_DIR/lib/patch-plugin.py" --revert || true

echo
echo "Done. A backup of your previous settings is kept at:"
echo "    ~/.codebuddy/settings.json.bak.codebuddy-sound-hooks"
echo "Remove the repo directory to finish: rm -rf $REPO_DIR"
