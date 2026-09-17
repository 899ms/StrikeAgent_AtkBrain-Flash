# 本仓库猎面 skills

Skill 源文件和本项目绑定，**不是**本机 `~/.claude` 或 `~/.pi` 全局环境。

| 路径 | 用途 |
|------|------|
| `skills/` | 本仓库 skills（源文件，进 git） |
| `backend/data/workspaces/<pid>/.agents/skills/` | 每个猎面会话的 cwd 副本（运行时拷贝） |

| skill | 赛道 |
|------|------|
| `kali-kit` | 共用：Kali 工具绝对路径 |
| `waf-bypass-methodology` | 共用：利用载荷被 WAF / 403 / 406 拦住时 |
| `recon-fanout` | CTF |
| `recon-spiral` | 红队 |
| `src-hunt-playbook` | SRC |

猎面运行时是 **Pi**。从者与角色工人的 `cwd` 是猎工作区。调度按御主方案并发拉起 Pi 进程（`--skill` 精确加载），工人禁止再开子进程。图工具走 `pi/extensions/atkbrain-tools.ts`。红队 / SRC 打开 Yakit 后，同一套 HTTP 桥会转发本机 Yak MCP（MITM、History、Fuzzer 等）；发包类强制走 MITM 下游代理池。证书与引擎是否匹配看控制台顶栏，不要混用 11432 / 11433 两套 CA。
