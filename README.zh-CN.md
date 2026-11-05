# codebuddy-sound-hooks

[English](README.md) | **中文**

CodeBuddy **干完活响一声**，**要你确认时也响一声**。

这样你就不用盯着聊天窗口等它转圈，可以去干别的事。

两端都支持：**JetBrains 插件**（PyCharm、IntelliJ IDEA 及其他 JetBrains IDE）和 **CodeBuddy 桌面 IDE**。

> 非官方项目，与腾讯云及 CodeBuddy 无隶属关系。

---

## 先看看适不适合你

| 问题 | 说明 |
|---|---|
| **你在用** | CodeBuddy 的 JetBrains 插件，或者 CodeBuddy 桌面版 |
| **你想要** | 不用一直盯着聊天窗口 |
| **你需要** | `python3`（macOS 自带；Linux 用 `apt install python3`） |
| **macOS** | 完整：完成音 + 等待确认音 |
| **Linux** | 完成音可用；等待确认音未实测（监听写的是 macOS 日志路径） |
| **Windows** | 完成音可用，需要 Git Bash；等待确认音不支持 |

不在 macOS 上的话，先看 [平台支持](#平台支持) 再装。完成音各平台都能用，第二个声音目前只有 macOS 有。

---

## 会听到什么

| 什么时候 | 什么声音 |
|---|---|
| 一轮回复结束 | Glass，一声清脆的"叮" |
| CodeBuddy 停下来等你确认 | Ping，一声短促提示 |

装完随便问它一句，然后走开。它干完就会响。

## 安装

### macOS / Linux

```bash
git clone https://github.com/GuangYangDev/codebuddy-sound-hooks.git
cd codebuddy-sound-hooks
./install.sh
```

就这样。下一轮对话开始生效，不用重启 IDE。

还想要"等待确认"那声？

```bash
./install.sh --with-watch     # 额外装一个小后台监听（macOS）
```

### subagent 的确认还得再走一步

**主 agent** 等你确认时，插件会往自己的日志里写一行，监听听得到。**subagent**（`task` 工具里跑的那些）等你确认时，插件走的是另一条代码路径，用 `logger.info` 报这件事——而 `console.info` 根本不会进日志文件，所以没有东西可听。

`lib/patch-plugin.py` 就是把那一个调用点从 `this.logger.info` 换成 `console.log`：

```bash
python3 lib/patch-plugin.py --apply    # 改完要重启 IDE
python3 lib/patch-plugin.py --status   # 显示 patched；CodeBuddy 更新后会变回 patchable
python3 lib/patch-plugin.py --revert   # 还原原始文件
```

它改的是已安装插件里的那个 bundle（那个开关只存在于那里），原文件备份在同目录的 `index.js.codebuddy-sound-hooks.orig`；只认一个锚点字符串，版本对不上就拒绝动手；写之前还会用 `node --check` 验语法。`uninstall.sh` 会自动还原。

代价说在前面：**CodeBuddy 一更新就把 bundle 换掉，补丁跟着没了。** 用 `--status` 就能发现，重新 `--apply` 一次即可。补丁要生效必须重启 IDE。

### Windows

hook 本身在 Windows 能用，但需要 **Git for Windows**：CodeBuddy 在 Windows 上是通过 Git Bash 执行 hook 的（不支持 cmd 和 PowerShell），而这个安装脚本是 bash 写的。

1. 装 [Git for Windows](https://git-scm.com/download/win)
2. 打开 **Git Bash**，进到仓库目录：

```bash
sh bin/notify.sh --test      # 确认能听到两声
python3 lib/settings.py add "$(pwd)/bin/notify.sh"
```

如果提示找不到 `python3`，去微软商店或 python.org 装一个，并确认它已经加进 Git Bash 的 PATH。

Windows 上卸载（bash 写的 `uninstall.sh` 在 Git Bash 里也能跑，但最少需要这一步）：

```bash
python3 lib/settings.py remove
```

### 确认装好了

```bash
sh bin/notify.sh --test        # 播放两档声音
python3 lib/settings.py status # 看加进去的两条 hook
```

## 日常操作

```bash
cd ~/codebuddy-sound-hooks   # pause 标记放在仓库根目录

touch pause      # 全部静音，立刻生效
rm pause         # 恢复

./uninstall.sh   # 移除 hook，并停掉监听
```

> `pause` 标记是**按脚本自身位置**找的，不是按你当前所在目录。在别的地方 `touch pause` 看着像成功了，实际什么也不会静音。仓库 clone 到别处的话，换成你的路径。

安装脚本只往 `~/.codebuddy/settings.json` 里**追加**，不会覆盖你已有的 hooks；动手前会先备份；重复执行什么都不会发生。

## 换声音

在 `settings.json` 的 hook 命令前面加环境变量：

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

把 `/path/to/codebuddy-sound-hooks` 换成你实际 clone 的位置——安装脚本写入的是绝对路径，hook 执行时不带你的工作目录。

末尾那个 `# codebuddy-sound-hooks` 别删。它不是随手写的注释：`lib/settings.py` 靠它认出哪条是自己加的，卸载时才能只删这一行、不动你其他 hooks。

macOS 在 `/System/Library/Sounds/` 里自带这些：Basso、Blow、Bottle、Frog、Funk、Glass、Hero、Morse、Ping、Pop、Purr、Sosumi、Submarine、Tink。

也可以加 `CB_VOLUME=0.5` 调音量。

## 不响了怎么办

**回复完成不响**

```bash
tail -5 events.log            # 有没有出现 Stop 记录
python3 lib/settings.py status
```

- 有记录但还是没声音 → 系统音量，或者声音文件路径不对。
- 根本没有记录 → hook 没触发。检查 `~/.codebuddy/settings.json` 里的命令路径，再确认 `sh bin/notify.sh --test` 能出声。

**等待确认不响**

```bash
python3 lib/watch-confirm.py --once   # 监听到底能不能匹配到东西
python3 lib/patch-plugin.py --status  # subagent 那条：patched 还是 patchable
```

- 是 subagent 在问、而 `--status` 显示 `patchable` → CodeBuddy 更新时把补丁覆盖了，重新 `--apply` 并重启 IDE。
- `--once` 有匹配但还是没声音 → 同上，音量或声音文件路径的问题。

在 Linux 或 Windows 上匹配为 0 是正常的，见下面。

## 平台支持

| 功能 | macOS | Linux | Windows |
|---|---|---|---|
| 完成音（hook `Stop`） | ✅ | ✅ | ✅ 需要 Git Bash |
| 等待确认音 | ✅ | ⚠️ 未实测 | ❌ 不支持 |
| 等待确认音（**subagent**） | ✅ 需要[插件补丁](#subagent-的确认还得再走一步) | ⚠️ 未实测 | ❌ |
| 监听开机自启 | ✅ launchd | ❌ 手动跑 | ❌ |

"等待确认"没有 hook 可用（原因见下面），只能读 CodeBuddy 自己的日志。目前只认 macOS 下的路径：

- `~/Library/Logs/JetBrains/*/fusion/logs/*/fusion.log`
- `~/Library/Application Support/CodeBuddy CN/logs/*/window*/exthost/Tencent-Cloud.coding-copilot/*.log`

如果你在 Linux 或 Windows 上找到了对应的路径，非常欢迎提 PR。

## 为什么"等确认"不用官方 Notification 事件

CodeBuddy 的 hooks 文档里有 `Notification` 事件，看着正合适。但它在 IDE 里**从来不触发**。

执行器是好的，问题在上面：四个能触发它的入口（`notifyPermissionPrompt`、`notifyIdle`、`notifyAuthSuccess`、`notifyElicitationDialog`）在插件里只有定义、**没有任何调用者**，是没接线的死代码。用了一整天记下来的事件日志里，`Stop` 有 7 条，`Notification` 0 条。

所以：完成音走官方 `Stop` hook（两端可靠），等待确认音退回读日志。完整排查过程和代码证据在 [docs/findings.md](docs/findings.md)。

subagent 的确认又是第三条路（该文件第 6 节）：插件用 `logger.info` 报它，而那个输出不会进任何日志文件，所以才有那个可选的[插件补丁](#subagent-的确认还得再走一步)。

## 隐私

全部本地运行。hook 从 stdin 读事件 JSON、播个声音、往 `events.log` 追加一行（时间 + 事件名 + 客户端）。**没有任何网络代码**，上传不了任何东西，payload 里的工具入参和文件内容也从不读取、不落盘。

自己验证，把会改你配置的安装脚本也一起扫进去：

```bash
grep -rn "curl\|wget\|urllib\|requests\|socket" bin lib *.sh    # 无输出
```

细节见 [PRIVACY.md](PRIVACY.md)。

## 工作原理

```
CodeBuddy 一轮回复结束
    └─ hook "Stop"        → bin/notify.sh          → 播完成音
CodeBuddy 停下来等你
    └─ 日志监听           → lib/watch-confirm.py   → 播确认音
        ├─ 主 agent   : state_update → waiting_user_input
        └─ subagent   : [SubagentToolListener] 那行，需先 --patch-plugin
```

`lib/settings.py` 负责合并 `settings.json`，所以装两次没关系，卸载也不会碰你其他设置。

有个坑值得记下来：`Stop` hook 绝对不能往 stdout 写东西。CodeBuddy 会把 Stop hook 的 stdout 显示在对话里，等于往模型的上下文里塞垃圾。`bin/notify.sh` 保证 stdout 为空，并且始终 `exit 0`（Stop hook 退出码 2 会让 agent 不停止、继续干活）。

## 许可证

MIT
