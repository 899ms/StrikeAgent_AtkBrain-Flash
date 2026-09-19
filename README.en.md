<p align="center">
  <a href="README.md">中文</a>
</p>

<p align="center">
  <img src="docs/assets/icon.svg" width="128" height="128" alt="StrikeAgent" />
  <img src="docs/assets/times.svg" width="48" height="128" alt="×" />
  <img src="docs/assets/brand.jpg" width="128" height="128" alt="Yean-Sec" />
</p>

<p align="center">
  <sub>StrikeAgent × Yean-Sec</sub>
</p>

<h1 align="center">StrikeAgent_AtkBrain-Flash</h1>

![This project proposes: self-loop · self-supervise · self-evolve](docs/assets/coined-triad.gif)

Built by Yean-Sec to explore what AI can actually do in authorized offensive security — something with its own ideas, not another generic “AI pentest” wrapper.

The console looks simple. It is not. Flash is about staying on target while still growing the attack surface. Red-team re-rating and a second verification pass exist so findings are usable. The team’s private Pro build has been used on dozens of programs and well over a thousand authorized internet-facing environments.

## Architecture

The console schedules hunts; the attack graph drives the self-loop. The servant finishes a full round before asking the master. A human message in chat interrupts the current round. Runtime is Pi (`deepseek-flash`). For red team / blue team/SRC, the first HTTP hop is local Yakit MITM; the next hop is the egress proxy pool.

![StrikeAgent_AtkBrain-Flash architecture](docs/assets/architecture.png)

## Product screens

Overview:

![Product overview](docs/assets/main.gif)

Home and new task: single target or cluster; red team (getshell), CTF (flag), blue team/SRC.

![Home and new task](docs/assets/ScreenShot_2026-09-19_231256_939.png)

Project console: attack graph, timeline, findings, chat.

![Project console](docs/assets/ScreenShot_2026-09-19_230912_075.png)

Vulnerability library:

![Vulnerability library](docs/assets/ScreenShot_2026-09-19_235824_031.png)

## Delivery report

<p><i>This report is from a real authorized engagement.</i></p>

[Open HTML](docs/demo/intranet-lab-report.html)

![Report cover](docs/assets/report-cover.png)

![Executive summary](docs/assets/report-body.png)

![Critical path](docs/assets/report-path.png)

![Asset picture](docs/assets/report-assets.png)

## Ranking

Tsecbench v1 **1st place** (`StrikeAgent_AtkBrain-Flash`, 97.89 / 100). Tencent Security YunDing Lab’s agent evaluation board.

![Tsecbench ranking](docs/assets/ScreenShot_2026-09-19_193220_407.png)

## What we do for platform security

An unauthorized visitor does not get a login page, an API, or a password on the wire.

- **Random entrance:** 8-character path only in `backend/data/security_entry` (`0600`). `python -m atkbrain.panel` prints the URL.
- **No leaked subpaths:** Bare `:2334/` is the product page; `/login`, `/api`, `/.env` return 404.
- **Anti capture / replay / bruteforce:** RSA-OAEP in the browser; one-shot ticket (120s); username/IP lockouts.
- **Password:** Argon2id in SQLite; a `0600` copy on disk for operators with a shell (`panel`).
- **Session:** `HttpOnly` cookie; no `?token=`; Swagger off. HTTPS on `:2334` by default.

## Environment and install

Docker on Kali (host network):

```bash
git clone <this repo URL>
cd StrikeAgent_AtkBrain-Flash
# Enter the repo root (the directory that contains compose.yaml and .env.example)
cp .env.example .env
# Edit .env: set DEEPSEEK_API_KEY=your key (hunts need it; console still starts without it)
docker compose -f compose.yaml -f deploy/compose.build.yaml up -d --build --wait
# Build the image, start the container, return after healthcheck
docker compose exec atkbrain python -m atkbrain.panel
# Print the https login URL with the random entrance, and the current password (host shell only)
```

Open the **https** URL `panel` prints (accept the self-signed cert). First login is `admin` / `admin`; you must change it. Console `:2334`, API `:2333`. Do not fight local systemd for those ports.

Forgot the URL or password: run `panel` again. If it says there is no plaintext copy, set `ATKBRAIN_ADMIN_PASSWORD` and `ATKBRAIN_ADMIN_PASSWORD_RESET=1` in `.env`, then `docker compose up -d`; set RESET back to `false` afterwards.

Without Docker: `sudo scripts/atkbrain-up.sh`. Data lives in `backend/data/` (gitignored); upgrades do not overwrite it.

## License and disclaimer

**AGPL-3.0-only** — free for personal and open-source use. Commercial license: [gavenmiya@outlook.com](mailto:gavenmiya@outlook.com). See [LICENSE](LICENSE).

Only for environments you are explicitly authorized to test.

The chat group is full. Follow WeChat 「夜安团队SEC」 to be added.

![Yean-Sec WeChat official account](docs/assets/wechat-oa.png)
