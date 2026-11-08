# ARCH · 代码结构定稿

> v1.4 ｜ 2026-11-07 ｜ 对应 [SPEC.md](SPEC.md) v1.0 · [AGENT_PLAN.md](AGENT_PLAN.md)
> 状态：**M0–M2、首轮信任边界修复及回合账本已完成**；ReAct 和主动消息尚未实现。规则冲突以 SPEC 为准，选型冲突以 TECH 为准，结构冲突以本文为准。
> v1.1 变更：① 前端改为 **Vite + React + TS 的独立 SPA**；② 引入 **ports / adapters / services**，让模型、存储、部署、前端都能单独替换。
> v1.2 历史变更：新增 `/api/chat/stream`（SSE），当时边生成边下发；v1.4 改为提交后分条播放。整段接口 `/api/chat` 保留。
> v1.3 变更：身份否认配置移除；身份问题走普通对话；私密情境只用受控标签和固定文案；本人通知先入 inbox，再记录投递状态。
> v1.4 变更：增加 `turns` 账本、显式消息关联、并发去重和断流状态查询；SSE 播放已提交回复。

---

## 0. 一页结论

```
                     ┌────────────── web/（Vite + React + TS）──────────────┐
                     │  聊天页 · 分条播放 · PWA · VITE_API_BASE 可指向任意后端  │
                     └───────────────────┬──────────────────────────────────┘
                                         │  /api/*  (Cookie + X-Stand-In)
                                         ▼
uvicorn app.main:create_app --factory --workers 1 ── FastAPI ── services ── ports ◄── adapters
                                                   │                  ├─ files（persona / memory）
                                                   │                  ├─ sqlite（消息 / 状态 / 日志）
                                                   │                  ├─ llm（openai 兼容 / fake）
                                                   │                  └─ notify（控制台 / webhook）
                                                   └── APScheduler（30s tick）
```

六条不可动摇的结构约束：

| # | 约束 | 为什么 |
|---|---|---|
| 1 | `core/` 只依赖标准库 | 闸门、披露、打分、分条能毫秒级裸测 |
| 2 | **`services/` 只认 `ports.py` 里的协议**，不 import 任何 adapter | 换模型/换库/换存储不改业务代码 |
| 3 | 记忆是 JSON 文件，不进 SQLite | 可手改、可 diff、`private.json` 结构隔离、免迁移 |
| 4 | 私密记忆只以受控情境标签和固定文案进 prompt | SPEC §3.2；原文和自由文本 hint 不进模型 |
| 5 | 单 worker + `(日期, 任务id)` 幂等键 | 多 worker 会把一条午饭发 N 次 |
| 6 | 所有路径由 `STANDIN_ROOT` 推导，代码里没有绝对路径 | 换机器、进容器、挪目录都不改代码 |

---

## 1. 可迁移的五条（v1.1 的核心）

| 维度 | 做法 | 换的时候改什么 |
|---|---|---|
| **机器** | 路径全由 `STANDIN_ROOT` 推导；`data/` `persona/` `memory/` `config/` 四个目录可用环境变量覆盖 | 只改 `.env` |
| **平台** | 无 Windows 专有 API；时区走 `TZ`；文件用 `pathlib`；Docker 镜像 Linux | 无 |
| **模型** | `LLM_PROVIDER` 写任意名字（`fake` 是特例）+ `BASE_URL` + `MODEL`；`ChatModel` 协议只有一个方法 | DeepSeek ↔ OpenAI ↔ Qwen ↔ Ollama/vLLM ↔ 自托管 LoRA：改环境变量 |
| **前端** | SPA 独立构建；`VITE_API_BASE` 指向任意后端；后端也能同源托管 `web/dist` | 单独部署前端只改一个变量 |
| **存储** | `MessageRepo` / `StateRepo` / `ProactiveRepo` 等协议；SQLite 只是其中一种实现 | 换 Postgres：新增 `adapters/postgres/`，业务代码一行不动 |

部署形态三选一，同一份代码：

| 形态 | 命令 | 适合 |
|---|---|---|
| 本地开发 | `uv run uvicorn app.main:create_app --factory --reload` + `pnpm -C web dev` | 改代码 |
| 单机生产 | `docker compose up -d`（Caddy 自动 HTTPS） | 1 核 1G VPS |
| 裸机 | `uv run uvicorn ... --workers 1` + systemd | 已有反代 |

---

## 2. 分层

```
api/  ──►  services/  ──►  ports.py  ◄──  adapters/
                │                            ├─ files/
                └──►  core/（纯函数）         ├─ sqlite/
                                             ├─ llm/
                                             └─ notify/
web/（SPA，独立构建，只通过 HTTP 说话）
```

| 层 | 可以 import | 禁止 import | 职责 |
|---|---|---|---|
| `core/` | 标准库 | 本项目任何模块 | 纯函数/纯数据；无 IO、无 `now()`、无 `random` 全局 |
| `ports.py` | typing、`core.models` | 任何 adapter、框架 | 只有 `Protocol` 定义 |
| `adapters/files/` | 标准库、`core.models` | db、api、llm | 读 `persona/`、`memory/`；原子写 + mtime 热更新 |
| `adapters/sqlite/` | sqlalchemy、标准库、`core.models` | services、api | 唯一执行 SQL 的地方 |
| `adapters/llm/` | openai、标准库、`core.models` | db、api、services | `messages → text` |
| `adapters/notify/` | httpx、标准库、`core.models` | db、api | 发送 webhook，返回 pending/accepted/failed/unknown 回执 |
| `services/` | `core/`、`ports.py`、`config.py` | **任何 `adapters/`**、api、web | 编排：reply / messenger / report |
| `api/` | 全部（只做装配与传输） | — | 解析、鉴权、组装依赖、返回 JSON |
| `web/` | — | — | 渲染与播放延迟；不判断该不该发 |

> 可执行化：`test/test_layers.py` 用 `ast` 扫描 import，违反即红。

---

## 3. 目录（定稿）

```
stand-in/
├── pyproject.toml  uv.lock
├── README.md  SPEC.md  TECH.md  ARCH.md  LICENSE  .env.example  .gitignore
│
├── config/
│   ├── messaging.example.json      提交；`messaging.json` 为真实排班（gitignore）
│   └── safety.json                 危机/叫停/记录词表（提交，非私人）
│
├── persona/                        ← gitignore（人格资产）
│   ├── interview.md  persona.md  style-rules.md  fewshot.jsonl
├── persona-example/                提交：clone 即可跑 demo
├── memory/                         ← gitignore
│   ├── profile.json  events.json  promises.json  bits.json  private.json
├── memory-example/
│
├── app/
│   ├── main.py                     create_app + lifespan（bootstrap → 调度器 → 关闭）
│   ├── settings.py                 pydantic-settings：.env，路径全部由 root 推导
│   ├── config.py                   messaging.json / safety.json 的模型与加载
│   ├── bootstrap.py                建目录、迁移、生成 .env、校验人格缺项
│   ├── ports.py                    ★ 协议：ChatModel / MemoryStore / PersonaSource /
│   │                                 Notifier / MessageRepo / StateRepo / ProactiveRepo /
│   │                                 SendLogRepo / InboxRepo / TurnRepo
│   │
│   ├── core/                       ★ 纯函数
│   │   ├── models.py               枚举与 dataclass（§5.1）
│   │   ├── scoring.py              中文 bigram 相关度（检索 + 去重共用）
│   │   ├── prompt.py               八段装配 + persona_version
│   │   ├── situation.py            私密条目 → 情境标签（只出标签）
│   │   ├── guard.py                危机/找本人/静音/记录边界
│   │   └── delay.py                分条 + 打字延迟
│   │
│   ├── adapters/
│   │   ├── files/persona.py        读四件套，产出 PersonaCard / 缺项清单
│   │   ├── files/memory.py         MemoryStore 实现：加载、热更新、原子写、私密区独立入口
│   │   ├── sqlite/engine.py        create_engine + PRAGMA(WAL, busy_timeout, foreign_keys)
│   │   ├── sqlite/migrate.py       PRAGMA user_version + 顺序执行 migrations/*.sql
│   │   ├── sqlite/migrations/001_init.sql
│   │   ├── sqlite/migrations/002_owner_delivery.sql  003_turns.sql
│   │   ├── sqlite/tables.py  sqlite/repositories.py
│   │   ├── llm/openai_compat.py    openai SDK + 超时/重试
│   │   ├── llm/fake.py             开发与测试用
│   │   ├── llm/factory.py          按 LLM_PROVIDER 返回实现
│   │   └── notify/owner.py         控制台 + webhook
│   │
│   ├── services/
│   │   ├── reply.py                REPLY 编排（建立回合 → guard → prompt → llm → 提交 → 播放）
│   │   ├── handoff.py              先记录转接意图，再通知并保存回执
│   │   ├── messenger/tasks.py      messaging.json 热加载 + `--plan`
│   │   ├── messenger/gate.py       11 条闸门（纯函数）
│   │   ├── messenger/compose.py    生成 → 约束 → 去重 → 重写（生成器注入）
│   │   ├── messenger/scheduler.py  APScheduler + tick + 单事务落库
│   │   └── report.py               日报文本
│   │
│   ├── api/
│   │   ├── deps.py                 依赖注入：ctx、require_session、require_owner
│   │   ├── auth.py                 /c/{token}、/api/owner/login、限速
│   │   ├── chat.py                 /api/chat、/api/messages、/api/control、/api/state
│   │   ├── admin.py                /me 与 /api/owner/*（M5）
│   │   ├── health.py               /healthz
│   │   ├── web.py                  托管 web/dist（SPA fallback）
│   │   └── schemas.py              pydantic DTO（唯一出入边界）
│   │
│   └── web/                        Python 侧不存静态文件；dist 在仓库 web/dist
│
├── web/                            ★ Vite + React 18 + TS（独立工程）
│   ├── package.json  pnpm-lock.yaml  vite.config.ts  tsconfig.json  index.html
│   ├── public/                     图标等
│   ├── src/
│   │   ├── main.tsx  App.tsx
│   │   ├── api/client.ts  api/types.ts
│   │   ├── hooks/useChat.ts        消息、播放队列、错误与重试
│   │   ├── components/ChatView.tsx
│   │   ├── components/MessageBubble.tsx
│   │   ├── components/Composer.tsx
│   │   ├── components/TypingDots.tsx
│   │   ├── components/SettingsSheet.tsx
│   │   ├── components/DisclosureBanner.tsx
│   │   └── styles.css
│   └── dist/                       ← gitignore（构建产物，后端直接托管）
│
├── deploy/
│   ├── Dockerfile                  多阶段：node 构建 → python 运行
│   ├── docker-compose.yml          standin + caddy（profile: tls）
│   ├── Caddyfile
│   └── systemd/stand-in.service
│
├── scripts/                        import_chat / seed_memory / export_dataset / backup / make_icons
├── test/                           pytest（沿用现目录）
│   ├── conftest.py  test_layers.py  test_bootstrap.py  test_api.py
│   ├── test_prompt.py  test_delay.py  test_memory.py  test_isolation.py
│   ├── test_gate.py  test_guard.py  test_compose.py
│   └── blind-test.md
│
└── data/                           ← gitignore：app.db、backups/
```

---

## 4. 端口（`app/ports.py`）

一个协议一个方法，方便整体替换：

```python
class ChatModel(Protocol):
    def complete(self, messages, *, temperature, max_tokens) -> Completion: ...

class MemoryStore(Protocol):
    def chat_items(self) -> Sequence[MemoryItem]: ...
    def private_items(self) -> Sequence[MemoryItem]: ...
    def write(self, kind: str, items: Sequence[MemoryItem]) -> None: ...

class PersonaSource(Protocol):
    def load(self) -> PersonaCard: ...

class MessageRepo(Protocol):
    def add_her(self, text, *, client_msg_id, now) -> int: ...
    def add_him(self, text, *, parts, mode, prompt_version, task_id, usage, now) -> int: ...
    def recent(self, limit: int = 12) -> Sequence[StoredMessage]: ...
    def since(self, after_id: int, limit: int = 200) -> Sequence[StoredMessage]: ...
    def her_replied_since(self, dt) -> bool: ...

class StateRepo(Protocol):      get / set / muted_until / snoozed_until
class ProactiveRepo(Protocol):  sent_today / count_today / last_at / reserve_and_send
class SendLogRepo(Protocol):    log
class InboxRepo(Protocol):      add / unread / mark_read
class Notifier(Protocol):       notify(kind, text) -> DeliveryStatus
```

`services/reply.py` 只接收这些协议实例；测试时给内存假实现即可。

---

## 5. 契约

### 5.1 `core/models.py`

```python
Mode(REPLY, PROACTIVE) · Visibility(CHAT, PRIVATE)
ReasonCode: disabled · not-today · already-sent-today · daily-cap · not-yet ·
            missed-window · quiet-hours · muted-by-her · snoozed ·
            awaiting-her-reply · min-gap
Action: REPLY · CRISIS · CALL_OWNER · MUTE · SNOOZE · RECORD

MemoryItem(id, text, kind, tags, visibility, updated_at, expires_at, due, annual,
           situation, since, hint)
MemoryHit(item, score, why) · Situation(label, since) · DeliveryStatus
DelayPart(text, delay_ms) · PromptBundle(messages, version, sections)
GuardVerdict(action, reply_parts, state, notify, context)
PersonaCard(identity, style, banned, fewshots, missing) · FewShot(tags, her, me)
StoredMessage(id, role, mode, text, parts, created_at) · Completion(text, tokens_in, tokens_out)
```

所有跨层传值都用这些类型，别处不再出现"无名 dict"。

### 5.2 prompt 八段

| # | 段 | 来源 | 预算 |
|---|---|---|---|
| 1 | 身份 | `persona.md`（渲染 MODE） | ≤400 tok |
| 2 | 风格 | `style-rules.md` §1–§6 | ≤900 |
| 3 | 少样本 | `fewshot.jsonl` 按场景取 6 条 | ≤600 |
| 4 | 记忆 | `scoring.select` 3–5 条（仅 chat） | ≤300 |
| 5 | 情境 | 受控 `situation` 标签 + 固定文案 | ≤100 |
| 6 | 历史 | DB 最近 12 条 | ≤1200 |
| 7 | 输出契约 | 代码生成（REPLY 连发 / PROACTIVE 一条） | ≤200 |
| 8 | 反例集 | `style-rules.md` §7 | ≤150 |

`version = sha256(身份 + 风格 + 反例 + 整份 fewshot)`：只随人格文件变；私密条目**没有进入本函数的参数**。

### 5.3 存储

| 数据 | 存哪 | 说明 |
|---|---|---|
| 消息 / 回合 / 主动日志 / 状态 / 发件箱 | `data/app.db`（WAL） | 聊天用 `client_msg_id` 去重；主动任务用 `(day, task_id)` |
| 偏好 / 事件 / 承诺 / 梗 | `memory/*.json` | 人可手改；`select()` 只收 chat |
| 私密 | `memory/private.json` | `situation.py` 只接受受控标签；当前仅 `压力期`，hint 不进入 prompt |

表：`messages`（`client_msg_id UNIQUE`、`turn_id`、`prompt_version`、`parts_json`）、`turns`（状态、输入输出消息 ID、错误码）、`proactive_log`、`send_log`、`app_state`、`owner_inbox`（含投递状态）。DDL 见 `adapters/sqlite/migrations/`。迁移前的消息保留顺序，`turn_id` 为空。

### 5.4 HTTP

| 方法 | 路径 | 认证 | 说明 |
|---|---|---|---|
| GET | `/c/{token}` | token | 种 `sid` Cookie → 302 `/` |
| GET | `/` `/assets/*` | 页面 `sid`；assets 公开 | 托管 `web/dist`；**不能把 StaticFiles 挂 `/`**（会绕过 Cookie） |
| GET | `/sw.js` `/manifest.webmanifest` | 无 | 根路径，Service Worker 作用域才覆盖全站 |
| GET | `/api/state` | `sid` | 未读、静音状态、披露文案、`appName` |
| GET | `/api/messages?after_id=` | `sid` | 增量历史 |
| POST | `/api/chat` | `sid` | `{text, client_msg_id}` → `{parts:[{text,delay_ms}], mode, fixed, turn_id, message_id}` |
| POST | `/api/chat/stream` | `sid` | 同上入参，回复提交后返回 SSE：`start` → `part` → `delta` → `done` |
| GET | `/api/turns/by-client/{client_msg_id}`、`/api/turns/{turn_id}` | `sid` | 查询 `generating/committed/failed`、输入输出消息 ID 与错误码 |
| POST | `/api/control` | `sid` | `{action: mute\|snooze\|call_owner\|why_ai}` → 回执 |
| POST | `/api/owner/login` | 口令 | 种 `owner` Cookie（HMAC，不存明文） |
| GET | `/api/owner/*` | `owner` | 消息流 / 记忆 / 发送日志 / 日报（M5） |
| GET | `/healthz` | 无 | `{ok, db, jobs, version}` |

所有写请求要求 `X-Stand-In: 1`；错误体 `{error:{code,message}}`；模型失败一律 `503`，**不返回假回复**。

### 5.5 前端

- 技术：Vite 5 + React 18 + TypeScript，无 UI 框架；一个 `styles.css`。
- 播放：`fetch` + `ReadableStream` 解析已提交回复的 SSE；`delta` 追加到当前气泡，`part` 开新气泡，`done` 收尾。断流或刷新按 `client_msg_id` 查询回合并同步历史。
- 配置：`VITE_API_BASE`（默认空 = 同源）；开发用 Vite proxy 转发 `/api` `/c` `/healthz`。
- PWA：`vite-plugin-pwa`（manifest + 离线壳）；推送留到 P2。
- 状态：`useChat` 一个 hook 管消息、流式拼接、错误与重试；不引入状态库。

---

## 6. 三条主链路

### 6.1 她发消息

```
POST /api/chat 或 /api/chat/stream
  → require_session → TurnRepo.start（事务内创建回合和输入；并发去重）
  → guard.classify
       ├─ 非 REPLY → 固定话术 → 通知意图入 owner_inbox → 尝试投递并记录状态 → delay → TurnRepo.commit
       └─ REPLY    → memory.chat_items() → select(3–5)
                   → situation.labels(private_items)
                   → prompt.build_reply → version
                   → llm.complete（失败 503，回合标为 failed，保留输入）
                   → delay.plan（2–4 条）
                   → TurnRepo.commit（回复与回合状态同事务）→ 整段返回或 SSE 播放
```

### 6.2 信使 tick（30s）

```
tasks.load（mtime 变了才重读）→ 一次查好 GateContext
  → 每任务 gate.check → 原因码则写 send_log
  → compose（生成 → ≤20 字/黑名单/去重 → 重试 ≤2）
  → reserve_and_send（单事务：proactive_log + messages）
  → 异常才 notify.owner
```

### 6.3 后台

```
/me → 消息流 / 记忆库 / 发送日志 / 日报
PUT /api/owner/memory/{kind} → memory.write（tmp + os.replace）→ 缓存失效
```

---

## 7. 施工批次

| 批次 | 交付 | 验收 |
|---|---|---|
| **M0** ✅ | 后端骨架 + 前端工程可跑 | `uv run python -m app.bootstrap`；`/healthz` 通；`pnpm -C web build` 成功 |
| **M1** ✅ | 能聊（假模型可演示） | 打开 `/c/<token>` 发一句 → 2–4 条依次出现；`pytest` 绿 |
| **M2** ✅ | 记忆 + 隔离 | 私密 sentinel 在 prompt 中 0 次 |
| **M3** | 信使 | 11 条原因码逐条可复现；`--plan` 正确 |
| **M4** | 兜底 | 危机、找本人、记录和普通身份对话的场景回归 |
| **M5** | 后台 + 日报 | `/me` 可看、可改、可查"为什么没发" |
| M6 | 工具与容器 | 导入 100 条；`docker compose up` 起得来 |
| M7 | 上线 | HTTPS + 域名 + 备份 |

每批收尾：`uv run ruff check . && uv run mypy app && uv run pytest -q && pnpm -C web build`。

---

## 8. 测试矩阵

| 文件 | 断言 |
|---|---|
| `test_layers.py` | `core` 不 import 本项目；`services` 不 import `adapters`；`api` 不写业务规则 |
| `test_prompt.py` | 八段顺序；无 `{{` 残留；改人格版本变、改记忆不变 |
| `test_delay.py` | 条数 2–4；深夜更长；≤220 字 |
| `test_memory.py` | 阈值下空；过期失效；private 不进 chat |
| `test_isolation.py` | 私密原文 sentinel 0 次；标签恰好 1 次 |
| `test_gate.py` | 11 原因码 × 优先级；night 豁免；awaiting 跨 08:30 失效 |
| `test_guard.py` | 危机不调模型；身份问题走普通回复；静音写状态 |
| `test_compose.py` | 超长/黑名单/相似重写；两次失败返回 None |
| `test_api.py` | 无 Cookie 401；错 token 403；client_msg_id 不双落 |
| `test_bootstrap.py` | 空目录 → 建表、生成 .env、缺项清单 |

---

## 9. 施工前要你补的（不是代码）

| 项 | 现状 | 缺了会怎样 |
|---|---|---|
| `persona.md` 的 `{{名字/年龄/城市/职业/关系底色/相识}}` | 6 处空 | 模型自己编；第一屏也没名字 |
| `persona/fewshot.jsonl` 40–60 条 | 不存在 | 少样本段空 → 退回 AI 助手腔 |
| `memory/promises.json` 2–3 条 | 空 | 信使只剩"吃了没/降温了" |
| `memory/profile.json` 5–10 条 | 空 | 记忆检索永远空 |

`bootstrap` 会在启动摘要里列出缺项；缺 fewshot 只告警，不阻塞。

---

## 10. 决定记录

| # | 决定 | 理由 | 代价 |
|---|---|---|---|
| 1 | 记忆存 JSON，DB 只存消息/状态/日志 | 手改、diff、`private.json` 隔离、免迁移 | 换 Postgres 时记忆仍是文件 |
| 2 | `awaiting-her-reply` 跨 08:30 失效 | 否则没回晚安 → 次日早安永远不发 | 与 SPEC 原文措辞不同，已在 SPEC 加注 |
| 3 | 前端用 React + Vite（而不是纯静态 HTML） | 播放队列、抽屉、PWA、后续 /me 都省事 | 多一个构建步骤；部署需 dist |
| 4 | 引入 ports/adapters（而不是直接调用） | 换模型/换库/换存储不动业务层 | 多一层协议，文件多约 8 个 |
| 5 | 单仓库、前后端分目录、一个 Dockerfile | 一条命令部署；前端也能独立托管 | 前端构建产物需随镜像 |
