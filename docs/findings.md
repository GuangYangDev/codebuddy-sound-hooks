# Findings: why the `Notification` hook does nothing

Notes from building this, kept because they answer a question the official docs don't: *does the `Notification` hook work in the IDE, or only in the CLI?*

Tested against CodeBuddy JetBrains plugin `4.12.40032586` on macOS, November 2026.

## 1. `Stop` works, and works immediately

Adding `hooks.Stop` to `~/.codebuddy/settings.json` takes effect on the next turn — no IDE restart, no `/hooks` approval panel (the official CLI docs describe one; the IDE clients don't require it).

The payload delivered on stdin:

```json
{
  "session_id": "591b34...",
  "transcript_path": ".../history/<workspace-hash>/<session>/index.json",
  "cwd": "/",
  "hook_event_name": "Stop",
  "generation_id": "b7c7b1...",
  "model": "deepseek-v4.1-flash",
  "agent_type": "craft",
  "client": "JetBrains",
  "version": "4.12.40032586"
}
```

`client` distinguishes the two front ends: `JetBrains` for the plugin, `CodeBuddyIDE` for the desktop app. Both fired with the same config, which is why one `settings.json` covers both.

Note the tool names in `PreToolUse` payloads are Claude Code style — `Bash`, `Edit`, `Read` — not the IDE's internal `execute_command` / `read_file`.

## 2. `Notification` never fires

`hook-events.log` over a day of real use:

```
2026-11-01 02:01:50 Stop client=JetBrains
2026-11-01 02:02:41 Stop client=JetBrains
2026-11-01 02:03:23 Stop client=CodeBuddyIDE
2026-11-01 02:05:08 Stop client=JetBrains
2026-11-01 02:05:43 Stop client=CodeBuddyIDE
2026-11-01 02:06:33 Stop client=CodeBuddyIDE
2026-11-01 02:09:23 Stop client=CodeBuddyIDE
```

Zero `Notification` entries — while the plugin's own log recorded 13 `state_update: running→waiting_user_input` transitions in the same window. So the situations people would want to be notified about *did* happen; the hook just never ran.

## 3. The cause: the entry points are dead code

In the plugin's bundled extension (`vsix/extension/out/extension/index.js`):

```js
async notifyPermissionPrompt(...)  → executeNotificationHook(NotificationType.PERMISSION_PROMPT, ...)
async notifyIdle(...)              → executeNotificationHook(NotificationType.IDLE, ...)
async notifyAuthSuccess(...)       → executeNotificationHook(NotificationType.AUTH_SUCCESS, ...)
async notifyElicitationDialog(...) → executeNotificationHook(...)
```

`executeNotificationHook` builds the correct payload (`hook_event_name: "Notification"`, `message`, `notification_type`) and runs the registered commands. The executor is fine.

The problem is above it. Counting real occurrences:

```console
$ F=.../extension/index.js
$ grep -ao "executeNotificationHook" "$F" | wc -l    # 5
$ grep -ao "notifyPermissionPrompt"  "$F" | wc -l    # 1
$ grep -ao "notifyIdle"              "$F" | wc -l    # 1
$ grep -ao "notifyAuthSuccess"       "$F" | wc -l    # 1
```

`executeNotificationHook`: 1 definition + 4 call sites, all inside those four helpers.
Each `notify*` helper: **exactly one occurrence** — its own definition. Nothing calls them.

**Pitfall worth recording:** `grep -c` counts matching *lines*, and minified JS can be one enormous line, so `grep -c` reported `1` for everything and made the situation look identical. Use `grep -o ... | wc -l` when counting symbols in bundled JS.

## 4. Consequence for this project

| Moment | Mechanism | Reliable? |
|---|---|---|
| Turn finished | hook `Stop` | Yes, both clients |
| Waiting for confirmation | log watcher | JetBrains: yes. Desktop: only when `needUserConfirm` fires |

Signal used by the watcher:

- JetBrains plugin: `[AcpSessionEventHandler] state_update: running→waiting_user_input` in `fusion.log`
- Desktop IDE: `needUserConfirm: true` in `Tencent-Cloud.coding-copilot/腾讯云代码助手.log`

`running→waiting_user_input` is an ACP session state and has nothing to do with the four `Notification` types, so even if the dead code above were wired up, it would not automatically cover this case.

## 5. Things that look like signals but aren't

- **`~/.codebuddy/projects/<project>/<session>.jsonl` → `type: "turn-metrics"`.** Appears once per turn, which looks perfect, but it is **not** written in real time. One session's file stopped updating at 01:08 while the plugin's log recorded five more completed turns at 01:14–01:42. Unusable for live notification.
- **Desktop IDE session status.** Only `Working` / `Planning` / `Completed` exist — there is no "waiting" state, so `Completed` is the only usable completion signal there.
