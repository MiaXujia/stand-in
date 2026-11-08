# 部署

三种形态，同一份代码。

## 1. 本地开发

```bash
uv sync
uv run python -m app.bootstrap
pnpm -C web install
pnpm -C web dev            # 前端 5173，代理到 8000
uv run uvicorn app.main:create_app --factory --reload
```

## 2. 单机 Docker（推荐）

```bash
cp .env.example .env        # 填 CHAT_TOKEN / OWNER_PASSWORD / DEEPSEEK_API_KEY
docker compose -f deploy/docker-compose.yml --profile tls up -d --build
```

- `app` 只监听 `127.0.0.1:8000`，`caddy` 负责 80/443 与证书。
- 需要在 `.env` 里加 `DOMAIN=chat.example.com`，并把域名 A 记录指向这台机器。
- 数据在 `data/`、`persona/`、`memory/`、`config/`（以卷挂载，不进镜像）。
- 更新：`git pull && docker compose -f deploy/docker-compose.yml up -d --build`。

不用 TLS 时去掉 `--profile tls`，直接访问 `http://127.0.0.1:8000/c/<token>`。

## 3. 裸机 + systemd

```bash
sudo useradd -r -s /usr/sbin/nologin standin
sudo mkdir -p /opt/stand-in && sudo chown standin:standin /opt/stand-in
# 把仓库放到 /opt/stand-in，然后：
cd /opt/stand-in
uv sync --no-dev
uv run python -m app.bootstrap
pnpm -C web install && pnpm -C web build   # 或用 CI 构建好再拷 dist
sudo cp deploy/systemd/stand-in.service /etc/systemd/system/
sudo systemctl enable --now stand-in
```

前面用 Caddy/Nginx 终止 HTTPS，反代到 `127.0.0.1:8000`。

## 备份

```bash
# SQLite 热备份（WAL 下也可以）
sqlite3 data/app.db ".backup 'data/backups/app-$(date +%F).db'"
```

`scripts/backup.py`（M6）会做同样的事并保留 7 天。
`persona/`、`memory/` 是纯文本，直接一起打包即可。

## 检查清单

- [ ] `CHAT_TOKEN` ≥ 32 位，且只发给一个人
- [ ] `OWNER_PASSWORD` 独立于 token
- [ ] HTTPS 已启用（Cookie 会自动带 Secure）
- [ ] `data/` 与 `persona/`、`memory/` 不在 Git 里
- [ ] 只跑 **1 个 worker**（多 worker 会重复发主动消息）
