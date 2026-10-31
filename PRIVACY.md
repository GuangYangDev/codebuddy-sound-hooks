# Privacy

Short version: everything runs on your machine. Nothing is collected, uploaded, or shared. There is no network code in this project.

## What the scripts read

**bin/notify.sh** receives one JSON object on stdin from CodeBuddy's hook system. Fields include `hook_event_name`, `session_id`, `cwd`, `tool_name`, and `tool_input`. The script:

- reads only `hook_event_name` and `client`
- plays a sound based on the event
- appends one line to `events.log`: timestamp, event name, client name

It does **not** read, parse, or store `tool_input`, so command text and file contents inside the payload never touch disk.

Turn off the log entirely by making the directory read-only or by deleting `events.log` after use — the log is only for troubleshooting.

**lib/watch-confirm.py** reads the tail of CodeBuddy's own log files:

- `~/Library/Logs/JetBrains/*/fusion/logs/*/fusion.log`
- `~/Library/Application Support/CodeBuddy CN/logs/*/window*/exthost/Tencent-Cloud.coding-copilot/*.log`

It matches a single pattern per file (`state_update: running→waiting_user_input`, `needUserConfirm: true`) and remembers a byte offset. It does not copy, upload, or retain log content. Matched lines are not stored anywhere; only a generic `confirm needed [source]` line goes into `.watch.log`.

## What is written to disk

Inside the repository directory:

| File | Content |
|---|---|
| `events.log` | `2026-11-01 02:14:19 Stop client=JetBrains` |
| `.watch.log` | watcher startup lines and `confirm needed [source]` |
| `pause` | empty marker file, created by you, not by the scripts |

And in `~/.codebuddy/settings.json`, two hook entries pointing at `bin/notify.sh`. A backup of the file is written next to it as `settings.json.bak.codebuddy-sound-hooks`.

## Network

No HTTP requests, no telemetry, no analytics, no update checks.

Verify it yourself:

```bash
grep -rn "curl\|wget\|urllib\|requests\|socket" bin lib
```

That returns nothing. The only `http` string anywhere in this repo is the W3C DOCTYPE URL inside the launchd plist template — a document type declaration, not a fetch.

Installing anything from GitHub obviously involves the network; after that, this tool is silent.

## Removing everything

```bash
./uninstall.sh
rm -rf ~/codebuddy-sound-hooks
```
