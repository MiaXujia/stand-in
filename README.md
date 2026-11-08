# stand-in

一个只给一个人用的聊天网站。他会用特定的语气回她的话，会有事没事主动问一句，会记得他们之间的事。

**这不是通用聊天机器人，是一份私人作品。** 设计文档比代码重要，请先读文档。

## 文档

| 文件 | 内容 |
|---|---|
| [SPEC.md](SPEC.md) | 业务规格：三种角色、披露矩阵、记忆隔离、信使闸门、验收标准 |
| [TECH.md](TECH.md) | 技术方案：Python 选型、依赖、部署与开源清单 |
| [ARCH.md](ARCH.md) | **代码结构定稿**：分层、端口/适配器、目录、接口、施工批次 |
| [persona/interview.md](persona/interview.md) | 12 个自问问题 —— **从这里开始** |

## 技术栈

Python 3.12 · FastAPI · SSE 分条播放 · SQLite 回合账本（WAL）· uv ｜ Vite 5 + React 18 + TypeScript ｜ 单进程、单 worker

## 本地跑起来

最省事：双击 `start.cmd`，或者在自己的终端里：

```powershell
.\start.cmd
```

首次会自动建库、生成 `.env`、装依赖、构建前端，然后启动并**自动打开浏览器**。
之后每次就是起服务 + 开门。

手动等价命令：

```bash
uv sync
uv run python -m app.bootstrap      # 建库 / 生成 .env / 打印入口
pnpm -C web install && pnpm -C web build
uv run python -m app.serve          # 自动开浏览器；加 --no-open 可关
```

入口是一条带口令的链接（`http://127.0.0.1:8000/c/<CHAT_TOKEN>`），本地执行 `python -m app.bootstrap` 会显示；服务日志不打印口令。
**本机直接开 `http://127.0.0.1:8000/` 会自动登录**（`LOCAL_AUTO_LOGIN=true`，只对 127.0.0.1 且未经反代的请求生效）；
公网 / 局域网 / 反代后面仍然必须用带 token 的链接。

> 国内网络装前端依赖慢：`pnpm config set registry https://registry.npmmirror.com`

默认 `LLM_PROVIDER=fake`，方便先把流程跑通；填好 `DEEPSEEK_API_KEY` 后，把它改成 `deepseek`、`openai`、`qwen` 等任意名字（只有 `fake` 是特例，表示不联网）。

### 开发模式（热更新）

```bash
uv run uvicorn app.main:create_app --factory --reload
pnpm -C web dev        # http://127.0.0.1:5173，已代理 /api /c /healthz
```

### 手机试

```bash
pnpm -C web build
uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 1
# 手机浏览器打开 http://<电脑局域网 IP>:8000/c/<token>
```

## 部署

```bash
# 单机（含 Caddy 自动 HTTPS，需要 .env 里有 DOMAIN）
docker compose -f deploy/docker-compose.yml --profile tls up -d --build

# 只跑应用（自己在前面放反代）
docker compose -f deploy/docker-compose.yml up -d --build
```

镜像不含 `persona/`、`memory/`、`data/`——它们以卷挂载，数据留在你的机器上。
裸机部署见 [deploy/README.md](deploy/README.md)。

## 换模型

只改环境变量：`LLM_PROVIDER=openai` + `DEEPSEEK_API_KEY` + `BASE_URL` + `MODEL`。
DeepSeek / OpenAI / Qwen / Ollama / vLLM / 以后自托管的 LoRA 都是同一个入口。

## 三条不可妥协的规则

1. **她知道这是 AI。** 身份问题按普通对话回答；提示词要求如实，不用专门的固定回复，也不掩盖"消息被记录"。
2. **危机一律转真人。** 出现自伤相关表达时停止扮演，记录转接请求并尝试通知本人；通知状态不确定时提示她直接联系真人，不由模型判断。
3. **私密记忆不进提示词。** 禁区内容永远不出现在对话上下文里，只以"情境标签"的形式影响语气。

## 数据安全

`persona/`、`memory/`、`data/`、`config/messaging.json`、`.env`、`web/dist/` 已被 `.gitignore` 排除。
首次 `git push` 前跑一遍：

```bash
git status --short     # 不应出现上述路径
```

计划开源，因此仓库里只保留 `persona-example/`、`memory-example/`、`config/*.example.*`。
真实内容留在本地，永远不进版本库。

## 状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| 方案 | SPEC v1.0 / TECH v0.4 / ARCH v1.1 | ✅ |
| M0 | 骨架可启动（后端 + 前端工程） | ✅ |
| M1 | 能聊（假模型可演示、分条播放、兜底话术） | ✅ |
| M2 | 记忆检索 + 私密隔离（private.json 零进 prompt） | ✅ |
| M3–M7 | 信使/后台/工具/上线 | ⬜ |

## 许可证

Apache-2.0（待添加 `LICENSE`）

## 声明

本项目是私人陪伴工具，**不是心理健康服务，不能替代真人**。请勿用于冒充他人实施欺骗。
