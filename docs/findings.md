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

## 6. Subagent confirmations reach no log at all

Symptom, reported after a few weeks of use: a **subagent** (the `task` tool) stops and asks for approval, and no sound plays — while main-agent confirmations are fine on the same machine, same watcher.

### The main path prints twice

A main-agent confirmation produces two adjacent lines, and the second one is what the watcher matches:

```
[ToolListener][PERM-DIAG] onUserConfirmRequired called: toolCallId=call_01_..., toolName=execute_command, state=pending, conversationId=591b3410...
[AcpSessionEventHandler] state_update: running→waiting_user_input, eventId=ide-591b3410-...
```

Counted across the three log files that contain confirmations at all, the two lines always appear in equal numbers (11/11, 3/3, 3/3). The `state_update` is the reliable half, and it comes from `ToolListener`:

```js
const Rn = this.agentSessionManager.getSession(this.conversationId);
Rn && Rn.transition(Sn.AgentStateEvent.WAIT_USER_INPUT)
```

### The subagent path prints to a void

Subagent tools belong to the subagent's own tool manager, which carries a different listener:

```js
ar.SubagentToolListener = class SubagentToolListener {
  onUserConfirmRequired(ir, ar, tn, rn) {
    this.logger.info(`[SubagentToolListener] User confirmation required - toolCallId: ${ar}, toolName: ${tn.name}`);
    // ...then it only updates the chat's tool-call cache, so the approve button appears
  }
```

Three differences from the main path, each fatal on its own:

1. **No `console.log`.** The handler reports through `this.logger.info`.
2. **No state transition.** `WAIT_USER_INPUT` is dispatched in exactly two places — `ToolListener.onUserConfirmRequired` and the reactive-tool resume in `AgentSessionManager.executeAsync`. Neither runs for a subagent tool, so the session stays `running` and no `state_update` line is written.
3. **`logger.info` never leaves the process.** `LoggerImpl` is explicit about it:

```js
error(ir,ar){this.log(ir,ar,console.error.bind(console))}
info(ir,ar){["info","debug"].includes(this.level)&&this.log(ir,ar)}      // sink defaults to console.info
warn(ir,ar){["info","debug","warn"].includes(this.level)&&this.log(ir,ar,console.warn.bind(console))}
```

`AbstractLogger.log(msg, ctx, sink = console.info)`. The extension host forwards `console.log` / `warn` / `error` into `fusion.log` (that is why `[ToolListener][PERM-DIAG]` shows up, tagged `[DEBUG]`) but **not** `console.info`.

Verified by absence, which is the strong form here: `[AgentSessionManager]`, `[DispatchContextManager]` and `[SubagentToolListener]` all exist in the bundle, all log on every single step, and appear **zero** times in `~/Library/Logs/JetBrains/**` and in `idea.log` after weeks of use.

So a subagent waiting for approval writes nothing anywhere — not to `fusion.log`, not to `idea.log`, not to the desktop-style `needUserConfirm` log. This is not a matching problem; there is no unpatched signal.

Side note worth recording: with `"permissions": {"defaultMode": "fullAccess"}` in `~/.codebuddy/settings.json`, the main agent rarely asks at all, so **subagent confirmations are the common case** for that setup. The missing half of the feature is the half that gets used.

### What this project does about it

`lib/patch-plugin.py --apply` flips that one call site to `console.log`:

```diff
-this.logger.info(`[SubagentToolListener] User confirmation required - toolCallId: ...
+console.log(`[SubagentToolListener] User confirmation required - toolCallId: ...
```

The anchor is unique in every bundle shipped so far (checked on 4.12.x for both PyCharm and IntelliJ). The tool backs the original up as `index.js.codebuddy-sound-hooks.orig` next to the file, refuses to touch a bundle whose anchor is not exactly one match, runs `node --check` on the result before publishing it, and `--revert` (also called by `uninstall.sh`) restores the bytes.

The cost, stated plainly: **a CodeBuddy update replaces the bundle**, so the patch disappears. `--status` reports `patchable` again when that happens; re-run `--apply`. The IDE has to be restarted for the patched bundle to be loaded.
