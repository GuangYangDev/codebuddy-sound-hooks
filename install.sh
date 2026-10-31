#!/bin/bash
# codebuddy-sound-hooks installer
#
#   ./install.sh              install hooks only (least invasive, recommended)
#   ./install.sh --with-watch also install a background watcher for the
#                             "waiting for your confirmation" sound (macOS)
#   ./install.sh --dry-run    show what would happen, change nothing
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
NOTIFY="$REPO_DIR/bin/notify.sh"
WATCH="$REPO_DIR/lib/watch-confirm.py"
PLIST="$HOME/Library/LaunchAgents/com.codebuddy-sound-hooks.watch-confirm.plist"
LABEL="com.codebuddy-sound-hooks.watch-confirm"

WITH_WATCH=0
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --with-watch) WITH_WATCH=1 ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 1 ;;
    esac
done

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required (macOS: xcode-select --install; Linux: apt install python3)" >&2
    exit 1
fi

if [ ! -f "$NOTIFY" ]; then
    echo "missing $NOTIFY — did you clone the whole repo?" >&2
    exit 1
fi

chmod +x "$NOTIFY" 2>/dev/null || true

echo "==> configuring CodeBuddy hooks"
if [ "$DRY_RUN" -eq 1 ]; then
    echo "    would run: python3 $REPO_DIR/lib/settings.py add $NOTIFY"
else
    python3 "$REPO_DIR/lib/settings.py" add "$NOTIFY"
fi

if [ "$WITH_WATCH" -eq 1 ]; then
    echo "==> installing confirmation watcher"
    if [ "$(uname -s)" != "Darwin" ]; then
        echo "    automatic startup is only implemented for macOS."
        echo "    run it manually or under your init system:"
        echo "        python3 $WATCH"
    elif [ "$DRY_RUN" -eq 1 ]; then
        echo "    would write $PLIST and load $LABEL"
    else
        mkdir -p "$HOME/Library/LaunchAgents"
        cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(command -v python3)</string>
        <string>${WATCH}</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ProcessType</key><string>Background</string>
    <key>ThrottleInterval</key><integer>10</integer>
    <key>StandardOutPath</key><string>${REPO_DIR}/.watch.out.log</string>
    <key>StandardErrorPath</key><string>${REPO_DIR}/.watch.err.log</string>
</dict>
</plist>
EOF
        launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
        sleep 0.3
        launchctl bootstrap "gui/$(id -u)" "$PLIST"
        echo "    watcher loaded: $LABEL"
    fi
fi

echo
echo "Done. Test it now:"
echo "    sh $NOTIFY --test"
echo
echo "Then ask CodeBuddy something and wait for the sound."
echo "Silence everything temporarily:  touch $REPO_DIR/pause"
echo "Uninstall:                       $REPO_DIR/uninstall.sh"
