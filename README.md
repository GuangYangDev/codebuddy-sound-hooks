# codebuddy-sound-hooks

**English** | [中文](README.zh-CN.md)

A sound when **CodeBuddy finishes a turn**, or when it **stops and waits for you to confirm** something.

So you can go read something else instead of watching the chat window spin.

Works with both clients: the **JetBrains plugin** (PyCharm, IntelliJ IDEA, and other JetBrains IDEs) and the **CodeBuddy desktop IDE**.

> Unofficial project. Not affiliated with Tencent Cloud or CodeBuddy.

---

## Does this fit your setup?

| Question | Answer |
|---|---|
| **You use** | CodeBuddy JetBrains plugin, or the CodeBuddy desktop IDE |
| **You want** | To stop babysitting the chat window |
| **You need** | `python3` (already on macOS; `apt install python3` on Linux) |
| **macOS** | Full: finished sound + waiting-for-you sound |
| **Linux** | Finished sound works. Waiting-for-you is untested — the watcher looks for macOS log paths |
| **Windows** | Finished sound works, via Git Bash. Waiting-for-you not supported |

If you're not on macOS, read [Platform support](#platform-support) before installing. The "finished" sound works everywhere; the second sound is macOS-only for now.

---

## What you'll hear

| When | Sound |
|---|---|
| A turn finishes | Glass — a soft chime |
| CodeBuddy is waiting for you to confirm | Ping — a short blip |

After installing, ask CodeBuddy something and walk away. When it's done, you'll hear the chime.

## Install

### macOS / Linux

```bash
git clone https://github.com/GuangYangDev/codebuddy-sound-hooks.git
cd codebuddy-sound-hooks
./install.sh
```

That's it. Changes take effect on the next turn — no IDE restart.

Want the "waiting for you" sound too?

```bash
./install.sh --with-watch     # adds a small background watcher (macOS)
```

### Subagents need one more step

When the **main agent** waits for approval, the plugin writes a line into its own log and the watcher hears it. When a **subagent** (the `task` tool) waits for approval, the plugin reports it through a logger whose output never reaches that log — `console.info` is not forwarded, so there is nothing to watch. Measured, not assumed: full write-up in [docs/findings.md §6](docs/findings.md).

`lib/patch-plugin.py` makes that one call site visible, by switching it from `this.logger.info` to `console.log`:

```bash
python3 lib/patch-plugin.py --apply    # then restart the IDE
python3 lib/patch-plugin.py --status   # "patched" — or "patchable" after a CodeBuddy update
python3 lib/patch-plugin.py --revert   # put the original file back
```

It edits the installed plugin bundle (that is the only place the switch exists), keeps the original next to it as `index.js.codebuddy-sound-hooks.orig`, uses one anchor string, refuses to patch an unknown version, and syntax-checks the result with `node --check` before writing. `uninstall.sh` reverts it.

The trade-off is real: **a CodeBuddy update replaces the bundle and the patch is gone.** `--status` is how you notice; re-run `--apply`. Restarting the IDE is required for the patched bundle to load.

### Windows

The hooks themselves work on Windows, but you need **Git for Windows** — CodeBuddy runs hooks through Git Bash on Windows (it does not support `cmd.exe` or PowerShell), and this installer is a bash script.

1. Install [Git for Windows](https://git-scm.com/download/win)
2. Open **Git Bash**, then in the repo directory:

```bash
sh bin/notify.sh --test      # confirm you hear two sounds
python3 lib/settings.py add "$(pwd)/bin/notify.sh"
```

If `python3` is missing, install it from the Microsoft Store or python.org, and make sure `python3` is on PATH inside Git Bash.

To uninstall on Windows (the bash uninstaller also works from Git Bash, but this is the minimal step):

```bash
python3 lib/settings.py remove
```

### Check it worked

```bash
sh bin/notify.sh --test        # plays both sounds
python3 lib/settings.py status # shows the two hooks that were added
```

## Everyday use

```bash
cd ~/codebuddy-sound-hooks   # the pause flag lives in the repo root

touch pause      # silence everything, effective immediately
rm pause         # back on

./uninstall.sh   # remove the hooks and stop the watcher
```

> The `pause` flag is looked up **next to the scripts**, not in your current directory. Creating it somewhere else looks like it works but silences nothing. If you cloned the repo elsewhere, use that path.

The installer only **adds** to `~/.codebuddy/settings.json` — it never overwrites your existing hooks, it backs the file up first, and running it twice does nothing.

## Change the sound

Prepend an env var to the hook command in `settings.json`:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command",
        "command": "CB_SOUND_DONE=/System/Library/Sounds/Hero.aiff sh /path/to/codebuddy-sound-hooks/bin/notify.sh # codebuddy-sound-hooks" } ] }
    ]
  }
}
```

Replace `/path/to/codebuddy-sound-hooks` with wherever you cloned it — the installer writes an absolute path, and the hook runs without your shell's working directory.

Keep the trailing `# codebuddy-sound-hooks` comment. It is not decoration: `lib/settings.py` uses it to recognise its own entry, so uninstalling removes exactly that line and leaves your other hooks alone.

macOS ships these in `/System/Library/Sounds/`: Basso, Blow, Bottle, Frog, Funk, Glass, Hero, Morse, Ping, Pop, Purr, Sosumi, Submarine, Tink.

`CB_VOLUME=0.5` works too.

## No sound?

**Turn finished, but silent**

```bash
tail -5 events.log            # is a "Stop" line appearing?
python3 lib/settings.py status
```

- Line appears, still silent → system volume, or the sound file path is wrong.
- No line at all → the hook isn't firing. Check the command path in `~/.codebuddy/settings.json`, and confirm `sh bin/notify.sh --test` plays.

**Waiting for you, but silent**

```bash
python3 lib/watch-confirm.py --once   # does the watcher see anything at all?
python3 lib/patch-plugin.py --status  # subagent confirmations: patched or patchable?
```

- A subagent is asking and `--status` says `patchable` → CodeBuddy updated itself and replaced the patch. Re-run `--apply` and restart the IDE.
- `--once` shows a match but nothing was heard → same causes as above (volume, sound path).

Zero matches on Linux or Windows is expected — see below.

## Platform support

| Feature | macOS | Linux | Windows |
|---|---|---|---|
| Finished sound (hook `Stop`) | ✅ | ✅ | ✅ via Git Bash |
| Waiting-for-you sound | ✅ | ⚠️ untested | ❌ not supported |
| Waiting-for-you sound, **subagent** | ✅ + [plugin patch](#subagents-need-one-more-step) | ⚠️ untested | ❌ |
| Auto-start of the watcher | ✅ launchd | ❌ run manually | ❌ |

The watcher reads CodeBuddy's own log files to detect "waiting" (there is no hook for it — see [Why](#why-not-just-use-the-notification-hook)). It only knows the macOS log locations:

- `~/Library/Logs/JetBrains/*/fusion/logs/*/fusion.log`
- `~/Library/Application Support/CodeBuddy CN/logs/*/window*/exthost/Tencent-Cloud.coding-copilot/*.log`

If you find the equivalent paths on Linux or Windows, a PR is very welcome.

## Why not just use the `Notification` hook?

CodeBuddy documents a `Notification` hook that looks like exactly the right tool for "waiting for confirmation". **It never fires in the IDE.**

Its executor is wired up, but all four things that would call it (`notifyPermissionPrompt`, `notifyIdle`, `notifyAuthSuccess`, `notifyElicitationDialog`) exist only as definitions with zero callers — dead code in the shipped extension. A day-long event log recorded seven `Stop` events and zero `Notification` events.

So this project uses the official `Stop` hook for "finished" (reliable, both clients), and falls back to watching logs for "waiting for you". Full investigation, with the greps and payloads, is in [docs/findings.md](docs/findings.md).

Subagent confirmations need a third route again (§6 of that file): the plugin reports them through a logger whose output is not forwarded to any log file, so the optional [plugin patch](#subagents-need-one-more-step) exists to make that one line visible.

## Privacy

Everything runs locally. The hook reads the event JSON from stdin, plays a sound, and appends one line to `events.log` (timestamp + event name + client). **There is no network code** — nothing is uploaded, and tool inputs or file contents in the payload are never read or stored.

Verify it yourself, including the installer scripts (which are the ones that actually touch your config):

```bash
grep -rn "curl\|wget\|urllib\|requests\|socket" bin lib *.sh    # nothing
```

Details in [PRIVACY.md](PRIVACY.md).

## How it works

```
CodeBuddy turn ends
    └─ hook "Stop"            → bin/notify.sh          → play done sound
CodeBuddy waits for you
    └─ log watcher            → lib/watch-confirm.py   → play confirm sound
        ├─ main agent    : state_update → waiting_user_input
        └─ subagent      : [SubagentToolListener] line, after --patch-plugin
```

`lib/settings.py` handles the `settings.json` merge, so installing twice is harmless and uninstalling leaves every other setting untouched.

One gotcha: `Stop` hooks must never write to stdout. CodeBuddy shows a Stop hook's stdout inside the chat, which would inject junk into the model's conversation context. `bin/notify.sh` keeps stdout empty and always exits 0 (exit code 2 on a Stop hook makes the agent keep working instead of stopping).

## License

MIT
