<p align="center">
  <img src="docs/assets/icon.svg" width="128" height="128" alt="StrikeAgent" />
  <img src="docs/assets/times.svg" width="48" height="128" alt="×" />
  <img src="docs/assets/brand.jpg" width="128" height="128" alt="夜安团队 SEC" />
</p>

<p align="center">
  <sub>StrikeAgent × 夜安团队 SEC</sub>
</p>

<h1 align="center">StrikeAgent_AtkBrain-Flash</h1>

![本项目提出：自循环 · 自监督 · 自进化](docs/assets/coined-triad.gif)

此项目由夜安团队开发，旨在探索 AI 渗透方面的能力，希望做点有自己思想的东西而不是Ai千篇一律随便搞出来的

项目整体看似简单，实则经过多轮实战测试，倾注了团队大量心血。细节设计更是数不胜数：单单“不打歪又能获得更大攻击面”这一点，就让团队煞费苦心（Flash 版）。此外，为了避免 AI 给出的漏洞存在夸大或误报的情况，团队特别设计了红队二次评级和二次验证，让漏洞所见即所得、拿着就能用，等等这些小细节。

团队自用的Pro版本更是已经落地几十个项目超千个外网真实授权环境，所有努力只聚焦外网打点。专注于一点登峰造极

## 架构

控制台调度猎面；攻击图驱动自循环。从者整轮（含角色工人）打完再问御主，卡住或到周期才开口；对话框里的人工指令立刻打断本轮并强制改向。收工把可迁移手法蒸馏进记忆库，回灌下一局。猎面运行时是 Pi（`deepseek-flash`），不是 Claude Code。红队 / SRC 的 HTTP 第一跳是本机 Yakit MITM，下游仍是出口代理池；图工具走本机 HTTP 扩展，Yakit 全套能力走本机 Yak MCP。

![StrikeAgent_AtkBrain-Flash 架构](docs/assets/architecture.png)

## 产品页面展示

新建项目：单目标 / 集群；三条赛道——红队（getshell）、CTF（flag）、SRC（厂商清单挖洞）。

![新建项目](docs/assets/ScreenShot_2026-09-07_213431_146.png)

控制台：攻击图、时间线、漏洞、对话。

![控制台](docs/assets/ScreenShot_2026-09-07_220023_410.png)

内网横向：橙线为 RCE 路径，紫实线为已控跨主机，紫虚线为跳板可达。

![内网横向](docs/assets/ScreenShot_2026-09-07_220034_635.png)

## 交付报告

 <p><i>此报告为一次真实的授权业务场景</i></p>

交付报告：[打开 HTML](docs/demo/intranet-lab-report.html)

![交付报告封面](docs/assets/report-cover.png)

![交付报告执行摘要](docs/assets/report-body.png)

关键攻击路径：

![关键攻击路径](docs/assets/report-path.png)

资产画像：

![资产画像](docs/assets/report-assets.png)

## 排行榜

Cybench 官方认证榜单第 3 名（`deepseek-v4-flash`，84.13 / 100）。

![Cybench 榜单](docs/assets/cybench.png)

## 环境与安装说明

### Agent 部署提示词

把下面整段连同源代码交给任意能跑本机命令的 AI。它应按原文部署，不要改 skill 绑定方式、不要把路径写死成别人的机器。

```
你要在本机把 StrikeAgent_AtkBrain-Flash 从当前源代码部署到可打开控制台。目标系统是 Kali Linux（Debian 系、systemd、能 sudo）。不要用 Docker 当主路径。不要把仓库里的猎面 skill 装进 ~/.claude 或 ~/.pi。不要把任何路径写死成 /home/kali/桌面/... 或其它克隆者机器上的目录。

一、目录与进程纪律
- 仓库根记为 REPO（含 backend/、frontend/、scripts/、skills/、tools/、pi/）。
- 后端 :2333，前端 :2334。不要在临时 shell 里再起 python3 -m atkbrain.main 或 npm run dev，会和 systemd 抢端口。
- 后端解释器必须是 /usr/bin/python3（3.12+），包装到系统 Python，不要只装进 venv 却让 unit 跑系统 python。
- 数据、库、工作区、密钥、MITM CA 只写 backend/data/（已 gitignore）。不要提交 .env、*.db、workspaces、loot、atkbrain-claude.env、yakit-mitm-ca.pem。
- 启动/重启只用：sudo scripts/atkbrain-up.sh（首次）、sudo scripts/atkbrain-backend.sh restart、sudo scripts/atkbrain-frontend.sh restart。unit 名是 atkbrain-flash-backend.service / atkbrain-flash-frontend.service。
- 不要把 yaklang/yakit 源码拷进本仓库。本机已装 Yak 引擎即可；Flash 当 MCP 客户端，不 vendor Yakit。

二、依赖
- sudo apt 安装 python3 python3-pip python3-dev build-essential nodejs npm curl；导出 PDF 再装 libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info。
- pip：sudo /usr/bin/python3 -m pip install -r backend/requirements.txt --break-system-packages
- 前端：cd frontend && npm install（atkbrain-up.sh 前必须有 frontend/node_modules）
- 全局安装 Pi：sudo npm install -g @earendil-works/pi-coding-agent；本机 `pi --version` 能跑（DEEPSEEK_API_KEY，可选 ANTHROPIC_AUTH_TOKEN 别名）。
- 本机 `yak` 能跑（Yakit / Yaklang 引擎）。不要 git clone yaklang/yakit 进本仓库。PATH 里没有 yak 时，顶栏会一直「Yakit 未就绪」。
- 把当前 shell 里的 DEEPSEEK_* / ANTHROPIC_* / ATKBRAIN_* / PI_* 准备好后再 sudo scripts/atkbrain-up.sh。脚本会把密钥快照到 backend/data/atkbrain-claude.env（权限 600）。systemd 的 PATH 里要有 pi 和 yak。

三、Skill / 工具路径（最容易部署错）
猎面 Pi 的 cwd 是 backend/data/workspaces/<项目id>/，不是仓库根。Skill 和本仓库绑定，不是用户全局环境。图工具走 REPO/pi/extensions/atkbrain-tools.ts（本机 HTTP）。不要再装 Claude Agent SDK。Yakit 走本机 Yak MCP（Streamable HTTP），由后端发现或自拉，不要把 Cursor 的 mcp.json 抄进仓库。
- 源文件：REPO/skills/kali-kit、recon-fanout、recon-spiral、src-hunt-playbook、waf-bypass-methodology。只进 git，不要复制到 ~/.claude 或 ~/.pi，不要改 Pi 用户级 settings 来装 skill。
- 运行时：会话启动会把本赛道 skill 拷到该猎工作区 backend/data/workspaces/<pid>/.agents/skills/。Pi 用 --skill 精确加载。
- 调度按御主方案并发拉起角色工人（Python 拉 Pi 进程），不要用 Claude Code 的 Task/Agent。工人禁止再开子进程。
- kali-kit 不能用手写死本机路径。仓库里的 skills/kali-kit/SKILL.md 用占位符 <REPO>。真正给从者看的那份由 backend/atkbrain/agents/kali_kit.py 的 skill_markdown() 按 REPO_ROOT 生成（REPO_ROOT = backend 的上一级）。project_skills.install_into_workspace 会在拷贝后覆盖工作区里的 kali-kit/SKILL.md。部署时不要把 SKILL.md 改成某台机器的绝对路径。
- Kali 没有、仓库自带的脚本必须用仓库绝对路径调用（工作区 cwd 找不到相对路径）：
  python3 $REPO/tools/JSFinder/JSFinder.py -u <url> -ou js_urls.txt -os js_subs.txt
  bash $REPO/tools/bypass-403/bypass-403.sh http://<host> <path>
  禁止 which jsfinder / which bypass-403，也不要把这两份脚本复制进 /usr/bin。
- nmap / ffuf / nuclei 等用系统绝对路径（/usr/bin/...），清单在 kali-kit，禁止 which / ls /usr/share/wordlists。
- 不要把 kali-kit 全文塞进系统提示；从者需要路径时调用 skill kali-kit。CTF 开局读 recon-fanout，红队开局读 recon-spiral，SRC 开局读 src-hunt-playbook。利用 payload 被 WAF/403/406 拦住时再读 waf-bypass-methodology；路径级 401/403 仍走 kali-kit 的 bypass-403。

四、Yakit MCP 与 MITM 证书
- 红队 / SRC：从者 HTTP 第一跳必须是本机 MITM（默认从 127.0.0.1:8084 起找空闲口，范围 8084–8107），DownstreamProxy 必须是出口代理池。禁止 proxychains 与 MITM 叠跳，禁止出口开着时漏本机 IP。CTF 默认不进 MITM。
- Yak MCP：优先接本机已监听的全能力口 http://127.0.0.1:11433/mcp（`yak mcp --enable-all`）。Cursor 若占用 11432，不要去抢、不要拿 11432 的 CA 去验 11433 的 MITM。没有监听时后端会自拉 11433。
- 证书：后端用 MCP 工具 download_mitm_cert 落到 backend/data/yakit-mitm-ca.pem。顶栏「证书就绪」= 文件可读未过期，且能用这张 CA 校验当前 MITM 的 HTTPS 叶子证。引擎换口后旧 CA 作废，设置页再点一次「下载 MITM 证书」。
- 顶栏持续检测：Yakit 就绪 / 证书就绪 / 已验收的出口 IP（跟 MITM 打 icanhazip 的结果，必须等于池节点）。设置页有 Yakit 开关、备用下游、下载证书。

五、验收
curl -sS http://127.0.0.1:2333/api/health   期望 ok: true，claude_sdk.label 为「Pi 就绪」（字段名仍是 claude_sdk，含义是 Pi）；打开 Yakit 后 yakit.engine.label 为「Yakit 就绪」，yakit.cert.label 为「证书就绪」，yakit.mitm.verified 为 true
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:2334/   期望 200
浏览器打开 http://127.0.0.1:2334/
失败先看 backend/data/logs/backend.err.log、frontend.err.log、backend/data/yakit-mcp.log：缺包、端口占用、pi/yak 不在 unit 的 PATH、没快照密钥、或 CA 与当前 MCP 引擎不是一套。
```

### 环境

建议在 **Kali Linux** 上跑（执行层会调用本机已有的渗透工具）。其它 Debian / Ubuntu 也能起控制台，但工具不一定齐。


| 依赖            | 版本 / 说明                                                                                    |
| ------------- | ------------------------------------------------------------------------------------------ |
| 系统            | Kali / Debian 系，systemd，root（`sudo`）                                                       |
| Python        | `/usr/bin/python3`，**3.12+**。后端 unit 直接跑这个解释器，不要只用 venv 装包却不改 unit                         |
| Node.js / npm | **18+**（Pi 建议较新 Node）                                                                   |
| Pi            | 本机 `pi` 能用：`npm i -g @earendil-works/pi-coding-agent`，配好 `DEEPSEEK_API_KEY`           |
| Yak / Yakit   | 本机 `yak` 能用（Yakit 引擎）。Flash 接 Streamable HTTP MCP，不把 yakit 源码放进仓库                         |
| 端口            | **2334** 控制台，**2333** API；Yak MCP 默认 **11433**（全能力，不抢 Cursor 的 11432）；MITM **8084–8107** |
| 磁盘            | `backend/data/` 会写库、工作区、日志、报告、`yakit-mitm-ca.pem`                                              |


系统包（Kali / Debian）：

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-dev build-essential \
  nodejs npm curl
# 导出 PDF 报告时 weasyprint 需要这些库；不装也能跑渗透，导出 PDF 会失败
sudo apt install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
  libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info
```

安装 Pi：

```bash
sudo npm install -g @earendil-works/pi-coding-agent
pi --version
```

Yakit 引擎（本机 `yak`，不要把源码拷进本仓库）：

```bash
command -v yak
yak version   # 或 yak --version
```

没有 `yak` 时先按 [Yakit](https://github.com/yaklang/yakit) 安装 Yak 引擎。后端需要时会自拉：

```bash
yak mcp --transport streamable_http --host 127.0.0.1 --port 11433 --enable-all
```

Cursor 若已经在 `127.0.0.1:11432/mcp` 跑了一份 Yak MCP，留给 Cursor；Flash 用 11433 全能力口，两套 CA 不能混用。

模型密钥用环境变量即可，安装脚本会快照到 `backend/data/atkbrain-claude.env`（权限 `600`，不要提交进 git）：


| 变量                                           | 作用                            |
| -------------------------------------------- | ----------------------------- |
| `DEEPSEEK_API_KEY`                           | 大模型密钥                         |
| `ANTHROPIC_AUTH_TOKEN`                       | 密钥别名（有则自动填给 Pi）               |
| `ATKBRAIN_PI_BIN`                            | `pi` 可执行文件路径，默认 `pi`          |
| `ATKBRAIN_PI_MODEL` / `ATKBRAIN_CLAUDE_MODEL` | 默认 `deepseek-flash`           |
| `ATKBRAIN_API_TOKEN`                         | 非空则 API / WebSocket 要带令牌（可选）  |
| `ATKBRAIN_YAKIT_MCP_URL` / `yakit_mcp_url`   | 覆盖 MCP 地址；默认先找 `127.0.0.1:11433/mcp` |
| `ATKBRAIN_YAKIT_MCP_FULL_PORT`               | Flash 自拉 `--enable-all` 的端口，默认 `11433` |
| `ATKBRAIN_YAKIT_MITM_PORT`                   | MITM 首选口，被占则向后找空闲口（到 8107）     |


Debian 12+ 若 `pip` 报 `externally-managed-environment`，给系统 Python 装包时加 `--break-system-packages`（本仓库的 systemd unit 用的就是 `/usr/bin/python3`）。

### 安装

```bash
git clone <本仓库 URL>
cd StrikeAgent_AtkBrain-Flash
```

1. 前端依赖（`atkbrain-up.sh` 前必须有 `frontend/node_modules`）：

```bash
cd frontend
npm install
cd ..
```

2. 后端依赖（装到 **系统** `python3`，和 unit 一致）：

```bash
cd backend
sudo /usr/bin/python3 -m pip install -r requirements.txt --break-system-packages
cd ..
```

3. 把当前 shell 里的 `DEEPSEEK_*` / `ANTHROPIC_*` / `ATKBRAIN_*` / `PI_*` 准备好（没有的可以先 `export DEEPSEEK_API_KEY=...`），再一键交给 systemd：

```bash
sudo scripts/atkbrain-up.sh
```

脚本会安装并 enable `atkbrain-flash-backend.service`、`atkbrain-flash-frontend.service`，把模型相关环境变量写入 `backend/data/atkbrain-claude.env`，拉起后端 `:2333`、前端 `:2334`（崩溃会自动重启）。

浏览器打开 **[http://127.0.0.1:2334/](http://127.0.0.1:2334/)**。局域网其它机器用 `http://<kali-ip>:2334/`。

确认起来：

```bash
curl -sS http://127.0.0.1:2333/api/health
# 期望含 "ok": true，以及 claude_sdk.label 为「Pi 就绪」
# 打开 Yakit 后还期望 yakit.engine.label 为「Yakit 就绪」、yakit.cert.label 为「证书就绪」
# yakit.mitm.verified 为 true；yakit.engine.url 应是 11433 全能力口，不要拿别人的 11432 CA 去验

curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:2334/
# 期望 200
```

日志：`backend/data/logs/backend.log`、`backend.err.log`、`frontend.log`、`frontend.err.log`、`backend/data/yakit-mcp.log`。数据在 `backend/data/`，已进 `.gitignore`。MITM CA 在 `backend/data/yakit-mitm-ca.pem`，不要提交。

红队 / SRC 默认 5 个项目槽、CTF 默认 3 个，两道互不占槽，都可调到 20。项目内 Pi 工人不设上限。顶栏看槽位、Pi 就绪、Yakit 就绪、证书就绪和出口 IP；设置页管自建代理池、Yakit 开关、备用下游和下载 MITM 证书。

红队墙钟 12 小时硬停（拿到 shell 提前收工）；SRC 6 小时硬停、不限轮次、已验证高危/严重不停工；CTF 按遍次墙钟。红队 / SRC 打目标：HTTP 第一跳本机 MITM，Downstream 必须是顶栏出口代理池；无存活节点则拒绝出网，不会回落真实 IP。CTF 始终直连，默认不进 Yakit。侧栏版本对照 GitHub Release 只提示，不自动升级。

### 常见问题

**`health: DOWN`**  
刚 restart 时 uvicorn 还在加载，等几秒再 curl。一直挂就看 `backend.err.log`：缺包、端口占用、或 `pi` / `yak` 不在 `PATH`。

**前端 unit 起不来，提示先 `npm install`**  
`scripts/atkbrain-frontend.sh` 要求 `frontend/node_modules` 已存在。

**控制台显示 Pi 未就绪**  
本机 `pi` 不在 PATH，或 `atkbrain-claude.env` 里没有密钥。在已配好密钥的 shell 里再执行一次 `sudo scripts/atkbrain-backend.sh restart`（会重新快照环境变量）。

**红队 / SRC 打目标报拒绝直连**  
顶栏出口代理开着，但还没有存活节点。到设置页保存自建池，或等探活转圈出节点后再打。CTF 始终直连，不受影响。

**顶栏「Yakit 未就绪」**  
本机没有 `yak`，或 MCP 没起来。看 `backend/data/yakit-mcp.log`。确认 `ss -tlnp | grep 11433`。不要去抢 Cursor 占用的 11432。unit 的 PATH 里要有 `yak`，改完再 `sudo scripts/atkbrain-backend.sh restart`。

**顶栏「证书异常」**  
CA 还没下、已过期，或证书绑定的 MCP 口和当前引擎不是一套（例如用 11432 的 CA 去验 11433 的 MITM）。到设置页点「下载 MITM 证书」，落到 `backend/data/yakit-mitm-ca.pem`。换引擎后必须重下。

**顶栏出口 IP 和池子不一致**  
顶栏必须跟当前 MITM 打 icanhazip 的结果。Yakit 开着时下游应是池当前节点；池子切了会重绑 DownstreamProxy。不要把 Yakit 错误页里的 IP 当成出口。

**2334 / 2333 被占**  
`ss -tlnp | grep -E '2333|2334'`，停掉旧进程后再 `atkbrain-up.sh`。

**11432 / 11433 / MITM 口被占**  
11432 留给 Cursor 的 Yak MCP 也可以；Flash 用 11433。MITM 口被别人占用时后端会从 8084 向后找空闲口，不要把别人的 8084 当成自己的抓包口。

## 开源协议与免责声明

**AGPL-3.0-only** — 个人和开源使用免费。商业许可请联系 [gavenmiya@outlook.com](mailto:gavenmiya@outlook.com)。

本仓库默认按 [GNU Affero General Public License v3.0](LICENSE)（仅第 3 版，不含后续版本）开源：

- **个人 / 开源（免费）：** 可复制、修改、分发；通过网络提供服务时，必须向用户提供完整对应源代码，并以 AGPL-3.0-only 再许可。
- **商业许可：** 闭源修改、专有产品、SaaS，或无法 / 不愿履行 AGPL 源代码义务的部署，须向夜安团队 SEC 取得单独商业许可。联系：**gavenmiya@outlook.com**

AGPL 正文见 [LICENSE](LICENSE)。商业许可条款以邮件约定为准。

本软件仅限在已获明确授权的环境中使用。使用即表示你已获得目标环境的授权，并自行承担合规与后果。作者与夜安团队 SEC 不对滥用、数据损坏或法律纠纷负责。

交流群目前已满。关注公众号「夜安团队SEC」，联系我们拉进群。

![夜安团队SEC 公众号名片](docs/assets/wechat-oa.png)
