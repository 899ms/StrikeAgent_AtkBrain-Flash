<p align="center">
  <a href="README.md">English</a>
</p>

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

控制台调度猎面；攻击图驱动自循环。从者整轮（含角色工人）打完再问御主，卡住或到周期才开口；对话框里的人工指令立刻打断本轮并强制改向。收工把可迁移手法蒸馏进记忆库，回灌下一局。猎面运行时是 Pi（`deepseek-flash`），不是 Claude Code。红队 / 蓝队/SRC 的 HTTP 第一跳是本机 Yakit MITM，下游仍是出口代理池；图工具走本机 HTTP 扩展，Yakit 全套能力走本机 Yak MCP。

![StrikeAgent_AtkBrain-Flash 架构](docs/assets/architecture.png)

## 产品页面展示

新建项目：单目标 / 集群；三条赛道——红队（getshell）、CTF（flag）、蓝队/SRC（厂商清单挖洞）。

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

最新排名：Tsecbench v1 **第 1 名**（`StrikeAgent_AtkBrain-Flash`，97.89 / 100）。

Tsecbench 是由腾讯安全云鼎实验室推出的智能攻防 Agent 评测体系，专注于自动化红队与对抗性 AI 的能力验证。平台通过真实漏洞、生产级靶场与红蓝对抗环境，以统一跑分标准全面衡量 AI在自主渗透、漏洞挖掘与对抗博弈中的表现，用攻击视角量化防御短板，让智能攻防能力从此有据可依。

![Tsecbench 榜单](docs/assets/ScreenShot_2026-09-19_193220_407.png)

## 为了平台安全所做的努力

猎面打的是授权目标；开控制台的那台机器本身也按「外网能扫到端口」来收口。下面这些不是装饰，是为了未授权访问拿不到登录页、接口和明文口令。

- **随机登录地址。** 8 位大小写入口由本机 `secrets` 生成，只写在 `backend/data/security_entry`（权限 `0600`）。网页和 API 都不能查看或修改。只有这台机器上的 `scripts/atkbrain-panel.sh`（或 `cd backend && python3 -m atkbrain.panel`）能打印完整 URL。
- **没有入口就没有子目录。** 裸 `:2334/` 只显示产品介绍页。`/login`、`/admin`、`/api`、`/docs`、`/.env`、`/.git` 等猜测路径一律 **404**。局域网不带入口访问 `/api/health` 也是 404（探活用 `python3 -m atkbrain.healthcheck`，本机回环并带上入口）。
- **防抓包看见明文口令。** 浏览器先用 RSA-OAEP SHA-256 加密再 POST。HTTP 旁路抓包拿不到登录口令明文。没有 TLS 时主动中间人仍可能换公钥，对外请在前面加 HTTPS。
- **防重放。** 每次登录先领一次性 ticket（120 秒过期），密文里还有 nonce 和时间戳；ticket 用过即废，抓到的包重放无效。
- **防爆破。** 失败按用户名（15 分钟内 5 次 → 锁 15 分钟）和 IP（1 小时内 20 次 → 锁 1 小时）写入 SQLite，重启清不掉。用户不存在也会走一遍 Argon2，避免用耗时判断账号是否在库里。
- **口令：库里只存哈希，本机可给有 shell 的人看。** Argon2id 进 SQLite。明文另写 `backend/data/admin_bootstrap.secret`（权限 `0600`）。网页和 API 读不到；`python -m atkbrain.panel` 可以打印。第一次登录会作废出厂 `admin` / `admin`；设置里改密后同样写入该文件。
- **会话与接口收口。** Cookie `HttpOnly` + `SameSite=Lax`；不用 `?token=` 查询串；登录和改密校验 Origin/Referer。OpenAPI / Swagger 关闭，不回 `Server` 头。

## 环境与安装说明

### Docker 一键部署

Linux（Kali）上与本机 systemd 同一套功能：控制台 `:2334`、API `:2333`、Pi、skills/tools、Yakit MCP `:11433`、MITM `8084–8107`、出口代理池、登录、数据在 `backend/data/`。容器走 **host 网络**，猎面里的 `127.0.0.1`、本机代理、本机靶场和本机跑法一样。

不要和已经在跑的 `atkbrain-flash-backend` / `atkbrain-flash-frontend` 抢端口。先停本机 unit，或换一台没占用 2333/2334 的机器。

根目录 `Dockerfile` 仍是 TSecBench 托管镜像（无控制台前端、无 Yak，启动即拉题），**不要**拿它当日常控制台。

```bash
git clone <本仓库 URL>
cd StrikeAgent_AtkBrain-Flash
cp .env.example .env
# 编辑 .env：至少填 DEEPSEEK_API_KEY（或 ANTHROPIC_AUTH_TOKEN）
docker compose -f compose.yaml -f deploy/compose.build.yaml up -d --build --wait
```

浏览器不要直接打开根路径。先在本机执行：

```bash
docker compose exec atkbrain python -m atkbrain.panel
```

命令会打印带 **8 位随机入口** 的登录 URL 和当前口令。入口由本机 `secrets` 生成，只写在 `backend/data/security_entry`（权限 0600）；口令明文只写在 `backend/data/admin_bootstrap.secret`（权限 0600）。网页和 API 都不能查看或修改这两项。没有该路径时本机直接显示 StrikeAgent 产品介绍页（不跳转），`/login`、`/api/health`、`/docs` 也不会露出控制台。第一次打开登录页仍显示默认 **`admin` / `admin`**；登录后必须改密。若关掉页面没改成，默认口令作废，再用上面的 `panel` 命令读取系统生成的 8 位口令。之后在设置里改密，`panel` 同样能打印新口令。忘了入口或要换入口：必须有这台机器的 shell（`python -m atkbrain.panel` 查看；删掉 `security_entry` 后重启会再随机一个）。局域网把 URL 里的 IP 换成 Kali 地址即可。

`--wait` 等到本机探活通过再返回（`python3 -m atkbrain.healthcheck`，带入口、回环，外网扫不到）。第一次构建会拉 Node/Python 基础镜像、编前端、装 Pi 和 Yak，时间较长。

之后日常：

```bash
docker compose -f compose.yaml up -d --wait          # 已有镜像，只启动
docker compose -f compose.yaml logs -f atkbrain
docker compose -f compose.yaml restart
docker compose -f compose.yaml down
```

改过前端或后端源码后重新构建：再跑一遍带 `deploy/compose.build.yaml` 和 `--build` 的命令。

配置（`.env`，与本机环境变量同一套 `ATKBRAIN_*` / `DEEPSEEK_*`）：

| 变量 | Docker 默认 | 作用 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | （空） | 大模型密钥，猎面必填 |
| `ANTHROPIC_AUTH_TOKEN` | （空） | 密钥别名，入口会和 DeepSeek 互相同步 |
| `ATKBRAIN_ADMIN_USER` / `ATKBRAIN_ADMIN_PASSWORD` | `admin` / `admin` | 仅首次写入；登录后强制改密 |
| `ATKBRAIN_ADMIN_PASSWORD_RESET` | （空） | `1` 时用当前口令覆盖库里的哈希（不会再次自动轮换） |
| `ATKBRAIN_SECURITY_ENTRY` | （空=本机随机生成） | 只能 `off` 关掉（仅本机 `npm run dev`）；不能指定自定义路径 |
| `ATKBRAIN_HOST` / `ATKBRAIN_PORT` | `0.0.0.0` / `2333` | API 监听；`:2334` 由入口转到这里 |
| `ATKBRAIN_CORS_ORIGINS` | 本机 `2334` 与 `2333` | 开 Cookie 后不要用 `*` |
| `ATKBRAIN_YAKIT_MCP_FULL_PORT` | `11433` | 容器内自拉 `yak mcp --enable-all`，不抢宿主机 Cursor 的 11432 |
| `ATKBRAIN_YAKIT_MITM_PORT` | `8084` | MITM 首选口，被占则向后找到 8107 |

起来之后顶栏应出现 Pi 就绪、Yakit 就绪、证书就绪（镜像里已带 `yak`，首次启动会拉 MCP 并下载 MITM 证书，不用再去设置页开开关）。红队 / 蓝队/SRC 出网前仍要在设置页保存出口代理池。数据、库、工作区、`yakit-mitm-ca.pem`、`yakit-mcp.log` 都在仓库的 `backend/data/`（volume），不要提交。

验收：

```bash
docker compose exec atkbrain python -m atkbrain.panel
cd backend && python3 -m atkbrain.healthcheck
# 本机回环带入口；配好密钥并登录后的 health 才含 Pi/Yakit 详情
curl -sS -o /dev/null -D- http://127.0.0.1:2334/
# 无入口路径时根路径 200 介绍页，其它子路径 404
```

Docker Desktop / 非 Linux 没有 host 网络时再叠一份端口映射（Kali 上不要用，否则 MITM 和本机代理对不齐）：

```bash
docker compose -f compose.yaml -f deploy/compose.build.yaml -f deploy/compose.bridge.yaml up -d --build --wait
```

桥接网络里容器的 `127.0.0.1` 不是宿主机；本机代理和本机靶场写成 `host.docker.internal`。

### 升级与数据迁移

**升级不会覆盖本地历史测试数据。** 项目、攻击图、漏洞、对话、工作区、loot、报告、管理员口令哈希、8 位入口、代理 / Yakit 设置、MITM 证书都在 `backend/data/`（已 gitignore）。登录后的「立即更新」跑的是 `scripts/atkbrain-upgrade.sh <tag>`：检出该 GitHub tag，或用源码包覆盖，**都会跳过** `backend/data/`、`*.env`、`frontend/node_modules/`、`frontend/dist/`。Compose 把宿主机 `./backend/data` 绑进容器，所以 `--build`、重建容器、`docker compose down` 都不会删掉这份目录。

升级前后不要跑 `git clean -fdx`（会把被忽略的 `backend/data` 一起删掉）。不要另克隆一份仓库再起 Docker，还指望旧项目出现。有猎面在跑或排队时拒绝升级（HTTP 409）；先停猎，SQLite（`atkbrain.db` 以及 `-wal` / `-shm`）才一致。

**本机 systemd 实例 → 本机 Docker**

必须用**同一份克隆**。Docker 挂的就是这个仓库的 `backend/data/`；再 clone 一份等于空库。

```bash
# 1. 控制台里先停猎，再停 unit（会和 :2333 / :2334 抢端口）：
sudo systemctl stop atkbrain-flash-backend atkbrain-flash-frontend
sudo systemctl disable atkbrain-flash-backend atkbrain-flash-frontend   # 可选，避免开机又拉起

# 2. 给 compose 准备密钥（systemd 当时快照在 backend/data/atkbrain-claude.env）
cp -n .env.example .env
# 把 DEEPSEEK_API_KEY / ANTHROPIC_AUTH_TOKEN 写进 .env。
# 不要设 ATKBRAIN_ADMIN_PASSWORD_RESET，否则会用 .env 里的口令覆盖库里已改过的哈希。

# 3. 仍在这个目录：
docker compose -f compose.yaml -f deploy/compose.build.yaml up -d --build --wait
docker compose exec atkbrain python -m atkbrain.panel
```

8 位入口和你已经改过的密码都还在。库里已有管理员时，不会再写入首次的 `admin` / `admin`。

**把 systemd 实例迁到另一台机器的 Docker**

先停源机器后端，保证 `atkbrain.db` 和 `atkbrain.db-wal` 成对一致。整棵 `backend/data/` **连权限一起拷**（`security_entry`、`auth-rsa.pem`、`auth-session.key`、`atkbrain-claude.env` 是 `0600`）。模型密钥写到目标机 `.env`。目标机**第一次** `docker compose up` 之前就放好这份目录。如果那边已经起过、生成了新入口和空库：先停容器，用拷来的 `backend/data/` 整目录替换，再启动。不要把两套库手工合并。`backend/data/logs/` 可以不拷。

**只换 db 不等于完整迁移。** `atkbrain.db` 里有项目列表、攻击图、漏洞、时间线、记忆、管理员口令哈希。工作区路径是 `backend/data/workspaces/<项目 id>/`，库只记 id，文件在磁盘上。只换 db 的结果是：面板能打开旧项目，但工作区是空的，续跑、loot、缓存的 HTML 报告会对不上。

还在库外面、只换 db **带不过去** 的：

| 文件 | 不管会怎样 |
| --- | --- |
| `workspaces/`、`loot/`、`reports/` | 历史文件和可下载报告没了 |
| `security_entry` | 8 位入口变新的，旧 URL 进不去 |
| `proxy-settings.json` | 代理池、Yakit 开关、墙钟回到默认 |
| `yakit-mitm-ca.pem` | 证书要重新下 |
| `atkbrain.db-wal` / `atkbrain.db-shm` | 源端没停库就只拷 `.db`，会丢最后一批写入或把库弄坏 |

登录口令哈希在库里，所以只换 db 时，用的还是源机器改过的密码，不是 Docker 首次的 `admin` / `admin`。入口文件不跟着走，登录地址仍是目标机自己的 8 位。

只换 db 的前提：源后端先停干净，把 `atkbrain.db`、`atkbrain.db-wal`、`atkbrain.db-shm` **三个一起换**（没有 wal/shm 就只换 db）。目标机容器也要先停，换完再起。不要两套库对着跑的时候覆盖。要项目还能续跑、报告还能下，仍应整棵拷 `backend/data/`。只想面板上看见历史记录，换 db（加 wal）就够。

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
- 不要把 kali-kit 全文塞进系统提示；从者需要路径时调用 skill kali-kit。CTF 开局读 recon-fanout，红队开局读 recon-spiral，蓝队/SRC 开局读 src-hunt-playbook。利用 payload 被 WAF/403/406 拦住时再读 waf-bypass-methodology；路径级 401/403 仍走 kali-kit 的 bypass-403。

四、Yakit MCP 与 MITM 证书
- 红队 / 蓝队/SRC：从者 HTTP 第一跳必须是本机 MITM（默认从 127.0.0.1:8084 起找空闲口，范围 8084–8107），DownstreamProxy 必须是出口代理池。禁止 proxychains 与 MITM 叠跳，禁止出口开着时漏本机 IP。CTF 默认不进 MITM。
- Yak MCP：优先接本机已监听的全能力口 http://127.0.0.1:11433/mcp（`yak mcp --enable-all`）。Cursor 若占用 11432，不要去抢、不要拿 11432 的 CA 去验 11433 的 MITM。没有监听时后端会自拉 11433。
- 证书：后端用 MCP 工具 download_mitm_cert 落到 backend/data/yakit-mitm-ca.pem。顶栏「证书就绪」= 文件可读未过期，且能用这张 CA 校验当前 MITM 的 HTTPS 叶子证。引擎换口后旧 CA 作废，设置页再点一次「下载 MITM 证书」。
- 顶栏持续检测：Yakit 就绪 / 证书就绪 / 已验收的出口 IP（跟 MITM 打 icanhazip 的结果，必须等于池节点）。设置页有 Yakit 开关、备用下游、下载证书。

五、验收
登录地址用 scripts/atkbrain-panel.sh（或 cd backend && python3 -m atkbrain.panel）打印的带随机入口 URL。不要把裸 http://127.0.0.1:2334/ 当成控制台（那是产品介绍页）。
cd backend && python3 -m atkbrain.healthcheck
  期望 ok: true，claude_sdk.label 为「Pi 就绪」（字段名仍是 claude_sdk，含义是 Pi）；打开 Yakit 后 yakit.engine.label 为「Yakit 就绪」，yakit.cert.label 为「证书就绪」，yakit.mitm.verified 为 true
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:2334/   期望 200（介绍页）
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
| `ATKBRAIN_API_TOKEN`                         | 非空则 API / WebSocket 要带令牌（Pi / 脚本用；浏览器走登录会话） |
| `ATKBRAIN_ADMIN_USER`                        | 单管理员用户名，默认 `admin` |
| `ATKBRAIN_ADMIN_PASSWORD`                    | 首次启动写入 SQLite 的口令（只存 argon2id）；VPS 必须设 |
| `ATKBRAIN_ADMIN_PASSWORD_RESET`              | `1` 时用当前环境变量口令覆盖库里的哈希 |
| `ATKBRAIN_AUTH_NO_AUTH`                      | 仅 `1/true/yes/on` 关闭登录保护；空字符串不能关 |
| `ATKBRAIN_CORS_ORIGINS`                      | 逗号分隔来源，默认本机 Vite `2334`；开 Cookie 后不要用 `*` |
| `ATKBRAIN_SESSION_MAX_AGE_SEC`               | 登录起算的绝对过期秒数，默认 86400（24 小时）；到期必须重新登录 |
| `ATKBRAIN_YAKIT_MCP_URL` / `yakit_mcp_url`   | 覆盖 MCP 地址；默认先找 `127.0.0.1:11433/mcp` |
| `ATKBRAIN_YAKIT_MCP_FULL_PORT`               | Flash 自拉 `--enable-all` 的端口，默认 `11433` |
| `ATKBRAIN_YAKIT_MITM_PORT`                   | MITM 首选口，被占则向后找空闲口（到 8107）     |


Debian 12+ 若 `pip` 报 `externally-managed-environment`，给系统 Python 装包时加 `--break-system-packages`（本仓库的 systemd unit 用的就是 `/usr/bin/python3`）。

### 安装（本机 systemd，不用 Docker 时）

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

脚本会安装并 enable `atkbrain-flash-backend.service`、`atkbrain-flash-frontend.service`（2334 反代到 2333），把模型相关环境变量写入 `backend/data/atkbrain-claude.env`，拉起后端 `:2333`、控制台 `:2334`。前端会 `npm run build`，由后端托管。

浏览器地址用 **`scripts/atkbrain-panel.sh`**（或 `cd backend && python3 -m atkbrain.panel`）打印的带随机入口 URL，不要打开裸 `http://127.0.0.1:2334/`（会显示产品介绍页，不是控制台）。

库里还没有管理员时会写入 `admin` / `admin`，登录后强制改密。**放到 VPS 上必须改掉默认口令**。顶栏未登录会进这个登录口。Pi 和脚本仍用 `X-API-Token` 请求头，不要把口令写进 `localStorage`，也不要用 `?token=`。

首次设密示例（只在引导时把明文放进环境；写入哈希后从 unit 里拿掉口令，改密再用 `ATKBRAIN_ADMIN_PASSWORD_RESET=1`）：

```bash
export ATKBRAIN_ADMIN_USER=admin
export ATKBRAIN_ADMIN_PASSWORD='换成你的长口令'
sudo scripts/atkbrain-up.sh
# 之后不要把 ATKBRAIN_ADMIN_PASSWORD 长期留在 systemd 环境里
```

反代 HTTPS（Caddy 示例；后端仍是 HTTP，靠 `X-Forwarded-Proto` 给会话 Cookie 打上 `Secure`）：

```
atkbrain.example.com {
    reverse_proxy 127.0.0.1:2334
}
```

nginx 记得 `proxy_set_header X-Forwarded-Proto $scheme;`。没有 TLS 时主动中间人仍可换公钥；RSA 只防旁路抓包看见口令。会话 Cookie：`HttpOnly`、`SameSite=Lax`、`Path=/`，登录起算 24 小时绝对过期，登录与中间件共用同一套选项。

确认起来：

```bash
cd backend && python3 -m atkbrain.healthcheck
# 期望含 "ok": true，以及 claude_sdk.label 为「Pi 就绪」
# 打开 Yakit 后还期望 yakit.engine.label 为「Yakit 就绪」、yakit.cert.label 为「证书就绪」
# yakit.mitm.verified 为 true；yakit.engine.url 应是 11433 全能力口，不要拿别人的 11432 CA 去验

curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:2334/
# 期望 200（无入口时是产品介绍页）
scripts/atkbrain-panel.sh
# 打印真正的控制台 URL
```

日志：`backend/data/logs/backend.log`、`backend.err.log`、`frontend.log`、`frontend.err.log`、`backend/data/yakit-mcp.log`。数据在 `backend/data/`，已进 `.gitignore`。MITM CA 在 `backend/data/yakit-mitm-ca.pem`，不要提交。

红队 / 蓝队/SRC 默认 5 个项目槽、CTF 默认 3 个，两道互不占槽，都可调到 20。项目内 Pi 工人不设上限。顶栏看槽位、Pi 就绪、Yakit 就绪、证书就绪和出口 IP；设置页管自建代理池、Yakit 开关、备用下游和下载 MITM 证书。

红队墙钟 12 小时硬停（拿到 shell 提前收工）；蓝队/SRC 6 小时硬停、不限轮次、已验证高危/严重不停工；CTF 按遍次墙钟。红队 / 蓝队/SRC 打目标：HTTP 第一跳本机 MITM，Downstream 必须是顶栏出口代理池；无存活节点则拒绝出网，不会回落真实 IP。CTF 始终直连，默认不进 Yakit。版本落后时每次登录会弹出发行说明；控制台可点立即更新（`scripts/atkbrain-upgrade.sh <tag>`）。有猎面在跑或排队时拒绝升级。该脚本不碰 `backend/data/`（见上文 **升级与数据迁移**）。

### 常见问题

**`health: DOWN`**  
刚 restart 时 uvicorn 还在加载，等几秒再 curl。一直挂就看 `backend.err.log`：缺包、端口占用、或 `pi` / `yak` 不在 `PATH`。

**前端 unit 起不来，提示先 `npm install`**  
`scripts/atkbrain-frontend.sh` 要求 `frontend/node_modules` 已存在。

**控制台显示 Pi 未就绪**  
本机 `pi` 不在 PATH，或 `atkbrain-claude.env` 里没有密钥。在已配好密钥的 shell 里再执行一次 `sudo scripts/atkbrain-backend.sh restart`（会重新快照环境变量）。

**红队 / 蓝队/SRC 打目标报拒绝直连**  
顶栏出口代理开着，但还没有存活节点。到设置页保存自建池，或等探活转圈出节点后再打。CTF 始终直连，不受影响。

**顶栏「Yakit 未就绪」**  
本机没有 `yak`，或 MCP 还没起来。Docker 一键镜像已内置 `yak`，首次启动会自动打开开关并拉 MCP / 下证书，等十几秒；一直红就看 `backend/data/yakit-mcp.log`。本机 systemd 则确认 `ss -tlnp | grep 11433`，unit 的 PATH 里要有 `yak`。不要去抢 Cursor 占用的 11432。设置里关掉开关后不会再自动开。

**顶栏「证书异常」**  
CA 还没下、已过期，或证书绑定的 MCP 口和当前引擎不是一套（例如用 11432 的 CA 去验 11433 的 MITM）。到设置页点「下载 MITM 证书」，落到 `backend/data/yakit-mitm-ca.pem`。换引擎后必须重下。

**顶栏出口 IP 和池子不一致**  
顶栏必须跟当前 MITM 打 icanhazip 的结果。Yakit 开着时下游应是池当前节点；池子切了会重绑 DownstreamProxy。不要把 Yakit 错误页里的 IP 当成出口。

**顶栏把我送进登录口**  
设了 `ATKBRAIN_ADMIN_PASSWORD`（或库里已有管理员）后，浏览器必须走 `/login` 加密口令。Pi / 脚本继续用 `X-API-Token`。本机无 TLS 时 Cookie 不会带 `Secure`；反代 HTTPS 时要传 `X-Forwarded-Proto`。

**升级是不是把项目删了？**  
不会。历史在 `backend/data/`（SQLite、工作区、loot、报告）。升级脚本跳过该目录；Docker 只是把同一路径 bind mount 进去。项目消失只可能是目录被删了、跑过 `git clean -fdx`，或 Docker 是从另一份克隆起的。见 **升级与数据迁移**。

**只换 `atkbrain.db` 算不算迁移完了？**  
能带过去项目列表、图、漏洞、对话和管理员哈希；工作区、报告、8 位入口、代理 / Yakit 设置都不在库里。两边都要先停，`.db` 和 `-wal` / `-shm` 一起换。要续跑仍须整棵 `backend/data/`。见 **只换 db 不等于完整迁移**。

**2334 / 2333 被占**  
`ss -tlnp | grep -E '2333|2334'`。本机 systemd 和 Docker 不要同时开：先 `sudo systemctl stop atkbrain-flash-backend atkbrain-flash-frontend`，或 `docker compose -f compose.yaml down`。

**Docker：`container is unhealthy` / `--wait` 失败**  
看 `docker logs strikeagent-atkbrain-flash`。若是 `admin_password_reset` / `Input should be a valid boolean`，说明空的 `ATKBRAIN_ADMIN_PASSWORD_RESET=` 被写进了容器。`.env` 里不要留这一行空值；compose 默认已是 `false`。改完后不必重建镜像：

```bash
docker compose -f compose.yaml up -d
```

**Docker：`scripts/atkbrain-panel.sh` 报 `No module named 'pydantic'`**  
旧脚本走的是**宿主机** `/usr/bin/python3`。Compose 镜像把 pydantic 装在容器里。请用 `docker compose exec atkbrain python -m atkbrain.panel`。现在的 `scripts/atkbrain-panel.sh` 在 `atkbrain` 容器已启动时会自动进容器。

**公网浏览器打不开，本机 `curl 127.0.0.1:2334` 却是 200**  
云厂商安全组 / 防火墙放行 **TCP 2334**。`python -m atkbrain.panel` 打印的是容器看到的内网 IP，把主机名换成这台机器的公网 IP，**8 位入口不要改**。

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
