#!/bin/sh
# codebuddy-sound-hooks — play a sound when CodeBuddy finishes a turn.
#
# Called by CodeBuddy hooks. Event payload arrives as JSON on stdin.
#
# Hard rules (learned the hard way, see docs/findings.md):
#   1. Never write to stdout. A Stop hook's stdout is shown inside the chat,
#      which would pollute the model's conversation context.
#   2. Always exit 0. Exit code 2 on a Stop hook tells the agent to keep
#      working instead of stopping — a nasty surprise.
#   3. Play in the background. Hooks are synchronous with a 60s timeout.
#
# Manual test:
#   sh bin/notify.sh --test

set -u

# Runtime state (events.log, pause flag) lives in the repo root, so uninstalling
# is just "delete the directory".
SELF_DIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd)
CONFIG_DIR="${CODEBUDDY_SOUND_HOME:-$(cd "$SELF_DIR/.." 2>/dev/null && pwd)}"
EVENT_LOG="$CONFIG_DIR/events.log"
PAUSE_FLAG="$CONFIG_DIR/pause"
VOLUME="${CB_VOLUME:-1.0}"

# Override any of these with env vars in your settings.json hook command.
SOUND_DONE="${CB_SOUND_DONE:-}"
SOUND_CONFIRM="${CB_SOUND_CONFIRM:-}"

platform() {
    case "$(uname -s 2>/dev/null)" in
        Darwin) echo macos ;;
        Linux) echo linux ;;
        MINGW*|MSYS*|CYGWIN*|Windows_NT) echo windows ;;
        *) echo unknown ;;
    esac
}

default_done_sound() {
    case "$(platform)" in
        macos) echo "/System/Library/Sounds/Glass.aiff" ;;
        linux) echo "/usr/share/sounds/freedesktop/stereo/complete.oga" ;;
        windows) echo "C:/Windows/Media/Windows Notify System Generic.wav" ;;
    esac
}

default_confirm_sound() {
    case "$(platform)" in
        macos) echo "/System/Library/Sounds/Ping.aiff" ;;
        linux) echo "/usr/share/sounds/freedesktop/stereo/message.oga" ;;
        windows) echo "C:/Windows/Media/Windows Ding.wav" ;;
    esac
}

play_file() {
    [ -n "${1:-}" ] || return 0
    [ -f "$1" ] || return 0
    case "$(platform)" in
        macos)
            ( afplay -v "$VOLUME" "$1" >/dev/null 2>&1 & )
            ;;
        linux)
            if command -v paplay >/dev/null 2>&1; then
                ( paplay "$1" >/dev/null 2>&1 & )
            elif command -v pw-play >/dev/null 2>&1; then
                ( pw-play "$1" >/dev/null 2>&1 & )
            elif command -v aplay >/dev/null 2>&1; then
                ( aplay -q "$1" >/dev/null 2>&1 & )
            fi
            ;;
        windows)
            # Hooks run under Git Bash on Windows; borrow PowerShell to play.
            ( powershell.exe -NoProfile -Command \
                "(New-Object Media.SoundPlayer '$1').PlaySync()" >/dev/null 2>&1 & )
            ;;
    esac
}

play_done() {
    if [ -n "$SOUND_DONE" ]; then play_file "$SOUND_DONE"; else play_file "$(default_done_sound)"; fi
}

play_confirm() {
    if [ -n "$SOUND_CONFIRM" ]; then play_file "$SOUND_CONFIRM"; else play_file "$(default_confirm_sound)"; fi
}

# Used by lib/watch-confirm.py so the audio logic lives in one place.
if [ "${1:-}" = "--play-done" ]; then
    play_done
    exit 0
fi

if [ "${1:-}" = "--play-confirm" ]; then
    play_confirm
    exit 0
fi

if [ "${1:-}" = "--test" ]; then
    echo "platform : $(platform)"
    echo "done     : ${SOUND_DONE:-$(default_done_sound)}"
    echo "confirm  : ${SOUND_CONFIRM:-$(default_confirm_sound)}"
    play_done
    sleep 1
    play_confirm
    echo "Played both sounds. If you heard nothing, check system volume."
    exit 0
fi

PAYLOAD=$(cat 2>/dev/null || true)

# Extract a top-level string field without needing python/jq.
extract() {
    printf '%s' "$PAYLOAD" \
        | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" \
        | head -1
}

EVENT=$(extract hook_event_name)
CLIENT=$(extract client)

[ -f "$PAUSE_FLAG" ] && exit 0

case "$EVENT" in
    Stop) play_done ;;
    Notification) play_confirm ;;
    *) exit 0 ;;
esac

mkdir -p "$CONFIG_DIR" 2>/dev/null
printf '%s %s client=%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$EVENT" "${CLIENT:-unknown}" \
    >> "$EVENT_LOG" 2>/dev/null

exit 0
