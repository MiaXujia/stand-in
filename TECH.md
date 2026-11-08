# TECH · 初步技术方案

> v0.4 ｜ 2026-10-25 ｜ 对应 [SPEC.md](./SPEC.md) v1.0
> **变更**：v0.1 Node → v0.2 Python → v0.3 Java → **v0.4 Python（定稿）**。
> 定稿理由：后面要做 LoRA 微调，训练管线只有 Python 有现成实现。**语言不再变。**
> **结构以 [ARCH.md](./ARCH.md) v1.1 为准**：前端已改为 Vite + React + TS，新增 ports / adapters / services 分层；
> 本文 §7 的目录树与"纯静态前端"选型不再作为施工依据，其余（选型理由、微调管线、部署原则）仍然有效。
> 只回答两件事：**代码怎么组织**、**技术怎么选**。业务规则以 SPEC 为准。

---

## 1. 为什么最后是 Python

不是因为"AI 项目都该用 Python"，是因为你说了要做微调。三件事只有 Python 能低成本做：

| 微调必需的能力 | Python | Java |
|---|---|---|
| 导出 ChatML / ShareGPT 数据集 | `datasets` 一行 | 手写序列化，还得自己对齐 tokenizer |
| **只对 assistant 轮算 loss**（mask 掉她的话） | `trl` 内置 collator | 基本得自己实现 |
| LoRA / QLoRA | `peft` | 无成熟实现 |
| 评测与指标回归 | `pandas` + 自定义 | 全手写 |

代价也要认：类型安全弱。补法——`pydantic` 管边界（请求体、配置文件、记忆条目全部校验）、`ruff` + `mypy` 管静态检查、纯函数层写类型注解。这三样做齐，Python 的类型问题基本可控。

---

## 2. 开源决定了三件必须先做的事

这一节与语言无关，但比选型重要。

### 2.1 个人数据和代码物理隔离

仓库里最敏感的不是代码，是 `persona/`（你说话的规则）、`memory/`（她的偏好、你们的吵架、她的生理期）、`data/app.db`（全部对话）。

规则：**真实数据一律 gitignore；仓库里只有 `*-example` 模板。**

```
persona/                  ← gitignore     persona-example/   ← 提交
memory/                   ← gitignore     memory-example/    ← 提交
config/messaging.json     ← gitignore     config/messaging.example.json ← 提交
config/app.yaml           ← gitignore     config/app.example.yaml       ← 提交
data/                     ← gitignore（数据库、训练集、备份）
.env                      ← gitignore
```

首次启动 `bootstrap.py` 检查缺失项，从 `*-example` 复制并打印提示。陌生人 clone 下来能跑 demo，而任何人的隐私都不进版本库。

### 2.2 提交前自查

```bash
git status --short     # 看到 persona/ memory/ data/ config/messaging.json 就停手
git check-ignore -v data/app.db
```

第一次 `git push` 泄漏的东西，之后删掉也永远在历史里。

### 2.3 许可证与命名

- **Apache-2.0**（带专利授权）
- 仓库名、包名、README 里不出现真名或她的名字；示例人名统一 `A` / `B`
- 公开前 `git log --stat` 过一遍

---

## 3. 实现目标

8 块，各自可独立验收：

| # | 目标 | 验收方式 | 模块 |
|---|---|---|---|
| **G1** | 能聊的单页网站（手机可装主屏） | 打开 → 发一句 → 收到分条回复 | `web/` + `api/chat.py` |
| **G2** | 回复像本人，不像 AI 助手 | 40 条盲测 ≥60%（首版），最终 70–85% | `core/prompt.py` + `persona/` |
| **G3** | 记得住，私密记忆零泄漏 | pytest：私密原文不出现在任何 prompt | `core/memory.py` |
| **G4** | 12:00 主动问午饭，且不乱发 | 11 条原因码逐条可复现；重启不重发 | `messenger/` |
| **G5** | 身份如实回答，危机和叫停有确定性流程 | 身份问题走普通回复；危机和叫停场景逐条验收 | `core/guard.py` + `core/prompt.py` |
| **G6** | 你能看记录、改记忆、查"为什么没发" | `/me` 三页可用 | `api/admin.py` |
| **G7** | 聊天记录能批量导入成语料与记忆 | 一条命令产出 60+40 条 | `scripts/import_chat.py` |
| **G8** | 能导出一份可训练的 JSONL（P3 前置） | `finetune/data/train.jsonl` + 泄漏检查通过 | `scripts/export_dataset.py` |

**不做**：多用户、注册登录、语音、图片、流式 token、向量数据库、消息队列、微服务。

---

## 4. 技术选型

| 层 | 选型 | 备选 | 为什么 |
|---|---|---|---|
| 语言 | **Python 3.12+** | 3.11 | `zoneinfo`、性能、生态都已就位 |
| 包管理 | **uv** + `pyproject.toml` | poetry / pip | 秒级装依赖；可选依赖分组干净 |
| Web | **FastAPI** | Flask / Django | pydantic 校验 + OpenAPI 文档；静态文件够用 |
| ASGI | **uvicorn（单 worker）** | gunicorn | **必须 1 个 worker**，见 §13 坑① |
| 前端 | **纯静态 HTML/JS**，`StaticFiles` 托管 | Jinja2 / React | 一个聊天页不需要模板引擎；token 走 Cookie，页面保持静态 |
| 数据库 | **SQLite（WAL）** | Postgres | 单用户单进程；备份=拷文件 |
| 访问 | **SQLAlchemy 2.0 Core（不用 ORM 关系映射）** | 裸 sqlite3 / Django ORM | Core 的 `select()` 够表达，又避免 ORM 的隐式查询；5 张表不需要关系图 |
| 迁移 | **自写 `migrate.py`（`PRAGMA user_version`）** | Alembic | 30 行；不自建版本表就不引入新组件。以后要升 Alembic 有路径 |
| 调度 | **APScheduler 3.x（BackgroundScheduler，tz=Asia/Shanghai）** + 纯函数闸门 | asyncio 循环 | 两层分离：APScheduler 管"到点"，`gate` 管"该不该发"，后者才能单测 |
| 模型 | **DeepSeek（OpenAI 兼容）**，`openai` SDK | httpx 手写 | 官方 SDK 自带重试/超时 |
| 配置 | **pydantic-settings** | os.environ | 类型转换 + 启动即校验，配错立刻炸 |
| 语料 | **pandas** | 纯 stdlib | 切样本、去重、统计句长/emoji 分布 |
| 测试 | **pytest**（+ `pytest-cov`） | unittest | 断言短，参数化方便 |
| 静态检查 | **ruff** + **mypy** | flake8+black | 一个工具格式化和 lint，mypy 补类型 |
| 反代 | **Caddy** | Nginx + certbot | 自动 HTTPS |
| 守护 | **systemd** | Docker | `Restart=always` |
| 推送 | **pywebpush**（P2） | 无 | 见 §13 坑② |

---

## 5. 六个关键取舍

**① 全同步，不为了 async 而 async。**
端点用 `def`（FastAPI 自动丢线程池），SQLAlchemy 同步 Session，`openai` 同步 client。
并发量是 **1 个人**。端点保持同步；FastAPI 在线程池处理请求，SSE 迭代器分条播放已提交回复。

**② SSE 分条播放（v1.4 修订）。**
`/api/chat/stream` 先生成并提交完整回复，再按分条计划发送 `part/delta/done`。这样断流不影响回合结果，客户端可查账本恢复；首字需等待模型完成。整段接口 `/api/chat` 与它共用生成和提交入口。

**③ 不用 ORM 的关系映射，只用 Core。**
5 张表、没有复杂关系图。`Core` 的显式 `select` 可读、可解释、没有 N+1。

**④ 不用向量数据库。**
记忆 10²–10³ 条。中文 bigram + 标签加权 + 阈值足够，而且**可解释**——检索错了你看得见为什么。到 10⁴ 条再考虑。

**⑤ 不用 LangChain / LlamaIndex / 任何 agent 框架。**
提示词就 6 段固定结构，自己拼 150 行：完全可控、可版本化、可断言。框架会把它变成黑盒，而"私密记忆有没有漏进 prompt"这种断言恰恰必须做。

**⑥ 训练依赖不进运行时环境。**
`torch` 装完 2GB+，绝不能和线上服务共享 venv。放 `[train]` 可选依赖（或独立 venv），只在 `finetune/` 里用。这条写进 CI：`pip install -e .` 不装 torch。

---

## 6. 依赖清单

```toml
[project]
requires-python = ">=3.12"
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "pydantic-settings",
  "sqlalchemy>=2",
  "apscheduler>=3.10,<4",
  "openai>=1",
  "pandas",
]

[project.optional-dependencies]
push  = ["pywebpush"]                                   # P2
train = ["torch", "transformers", "trl", "peft",         # P3，独立环境
         "datasets", "accelerate"]
dev   = ["pytest", "pytest-cov", "ruff", "mypy"]
```

运行时 7 个包，无编译依赖，1G 机器装得下。

---

## 7. 代码目录

```
stand-in/
├── pyproject.toml
├── uv.lock
├── README.md · SPEC.md · TECH.md · LICENSE · .gitignore · .env.example
│
├── config/
│   ├── messaging.example.json / messaging.json      ← 后者 gitignore
│   └── app.example.yaml / app.yaml                  ← 后者 gitignore
│
├── persona/                      ← gitignore（你的人格资产）
│   ├── interview.md  persona.md  style-rules.md  fewshot.md
├── persona-example/              ← 提交（模板）
│   ├── persona.md  style-rules.md  interview.md
│
├── memory/                       ← gitignore
│   ├── profile.json  events.json  promises.json  bits.json
│   └── private.json              私密区：只存，永不进 prompt 原文
├── memory-example/
│   └── profile.json  events.json  promises.json  bits.json  private.json
│
├── app/
│   ├── main.py                   FastAPI 装配 + lifespan 起调度器
│   ├── settings.py               pydantic-settings：.env + config/*.json 校验
│   ├── bootstrap.py              首次启动：example → 真实文件；建表
│   │
│   ├── db/
│   │   ├── engine.py             create_engine + PRAGMA(WAL, busy_timeout, foreign_keys)
│   │   ├── schema.sql            建表（幂等键唯一索引）
│   │   ├── migrate.py            PRAGMA user_version
│   │   ├── tables.py             Table 定义
│   │   └── repositories.py       messages / memory / state / send_log
│   │
│   ├── api/
│   │   ├── auth.py               GET /c/{token} → 种 HttpOnly Cookie → 302 /
│   │   ├── chat.py               POST /api/chat、GET /api/messages
│   │   ├── admin.py              /me：消息流、记忆库、发送日志、日报
│   │   └── schemas.py            pydantic DTO（请求/响应边界）
│   │
│   ├── core/                     ★ 纯函数：无 IO、无 DB、时间靠参数传入
│   │   ├── agent.py              编排：guard → memory → prompt → llm → delay
│   │   ├── prompt.py             6 段式 system prompt + 版本哈希
│   │   ├── guard.py              危机词、找本人、静默指令、记录边界
│   │   ├── memory.py             检索打分 + 私密隔离
│   │   ├── situation.py          私密记忆 → 情境标签（只出标签，不出原文）
│   │   ├── delay.py              分条 + 打字延迟 + 深夜加长
│   │   └── models.py             Mode / MemoryItem / Situation / ReasonCode
│   │
│   ├── messenger/
│   │   ├── gate.py               11 条闸门（纯函数，返回原因码或 None）
│   │   ├── compose.py            生成：压缩、去重、长度约束
│   │   ├── scheduler.py          APScheduler 注册 + tick + 幂等写库
│   │   └── tasks.py              读 messaging.json，支持热加载
│   │
│   ├── llm/
│   │   ├── client.py             openai SDK + base_url + 超时重试
│   │   └── usage.py              token 记账（prompt 预算告警）
│   │
│   └── notify/
│       ├── owner.py              给你：webhook / 控制台 / 每日摘要
│       └── push.py               给她：Web Push（P2，先空实现）
│
├── web/                          静态前端（无构建）
│   ├── index.html                她的聊天页（含第一屏说明）
│   ├── admin.html                你的后台
│   ├── app.js · admin.js · style.css
│   ├── manifest.webmanifest      PWA
│   └── sw.js                     Service Worker（离线壳 + 推送，P2）
│
├── scripts/
│   ├── import_chat.py            聊天记录 → 清洗 → 切样本 → 60/40
│   ├── export_dataset.py         → finetune/data/*.jsonl（含泄漏检查）
│   ├── seed_memory.py            抽取偏好/事件/承诺，生成待你确认的 JSON
│   └── backup.py                 SQLite 热备份 + 7 天轮转
│
├── finetune/                     P3，独立环境，不进运行时
│   ├── configs/lora_qwen.yaml
│   ├── train.py                  trl SFTTrainer + peft LoRA
│   ├── evaluate.py               40 条盲测 + 风格指标回归
│   ├── data/                     ← gitignore（训练集绝不进库）
│   └── README.md
│
├── tests/
│   ├── test_gate.py              11 条原因码
│   ├── test_guard.py             危机、找本人和普通身份对话
│   ├── test_isolation.py         私密记忆零泄漏（关键）
│   ├── test_delay.py             分条与深夜加长
│   ├── test_dataset.py           训练集泄漏检查
│   └── blind_test.md             40 条盲测记录表
│
└── data/                         ← gitignore
    ├── app.db
    └── backups/
```

### 7.1 分层规矩（违反就别合）

| 层 | 可以 | 不可以 |
|---|---|---|
| `core/` | 纯函数、字符串、打分 | 碰 DB、发 HTTP、读 `datetime.now()`（时间由参数传入） |
| `db/` | 唯一碰 SQLAlchemy 的地方 | 拼提示词、调模型 |
| `api/` | 解析请求、调 core、返回 JSON | 写业务规则 |
| `messenger/` | 调 gate/compose/repository | 在 `gate` 里读当前时间 |
| `web/` | 渲染、延迟播放 | 存状态、判断该不该发 |
| `finetune/` | 读库、写 jsonl、训练 | 被 `app/` 导入（反向依赖禁止） |

`core/` 纯函数是整套设计的关键：危机和控制闸门能 pytest 裸跑（毫秒级），你才敢天天改规则；时间从参数传入，才能测"跨午夜""她没回"。

---

## 8. 数据流

### 8.1 她发消息

```
浏览器 POST /api/chat {text}
   │
   ├─► guard.classify(text)
   │      ├─ 危机      → 停扮演 + notify.owner + 固定话术（不走模型）
   │      ├─ 找本人    → notify.owner + 固定回执
   │      ├─ 静音/在忙 → 写 state + 固定回执
   │      └─ 正常      → 继续
   │
   ├─► memory.retrieve(text)
   │      ├─ visibility=chat    → 最多 4 条原文
   │      └─ visibility=private → situation.tag() 只产出 {"situation":"压力期"}
   │
   ├─► prompt.build(persona, style, fewshot, hits, mode="REPLY")
   │      └─ 返回 (system, version=hash)
   │
   ├─► llm.client.chat(messages)                ← DeepSeek / 兼容端点
   │
   ├─► delay.split(text) → [{"text":…, "delay_ms":…}, …]
   │
   ├─► 落库（消息、prompt_version、token 用量、延迟）
   │
   └─► {"messages":[…]} → 前端逐条出现
```

### 8.2 信使触发

```
APScheduler(30s) → tick()
   ├─ tasks.load()（文件变了就重读）
   ├─ for task: gate(task, state, now) → 原因码 | None
   │      None → compose(task)
   │              ├─ 生成 → 超长压缩 → 与近 10 条比相似度 → 重写
   │              ├─ 落库 + 幂等键 (date, task_id)   ← 唯一索引兜底
   │              └─ notify.push（P2；P1 只落库，她打开看到未读）
   └─ 每条结果写 send_log（含原因码，供 /me 查"为什么没发"）
```

---

## 9. 微调管线（P3，但目录从现在留好）

### 9.1 什么时候才做

**提示词连续两轮盲测停在 60–70% 不再上涨**，才动微调。
先微调会掉进两个坑：只有 200 条数据 → 学成复读机；没有可靠的评测基线 → 分不清是变好还是变坏。

### 9.2 数据从哪来

```
data/app.db（messages 表是唯一真相源）
        │
        ▼  scripts/export_dataset.py
   ├── train.jsonl    ChatML：system=当时那版人格卡, user=她, assistant=你
   ├── valid.jsonl    5%
   └── eval.jsonl     40 条盲测集 —— 永不进训练
```

三条硬纪律：

1. **只对 assistant 轮算 loss**，user token 全部 mask（`trl` 的 `DataCollatorForCompletionOnlyLM`）。不 mask 会学成"模仿她的说话方式"。
2. **eval 集按 `message_id` 从训练集剔除**，并用相似度做二次检查（同一件事的变体也算泄漏）。
3. **system prompt 用训练时那版**——`messages.prompt_version` 落库就是为这个。微调后换了人格卡，风格会当场崩。

### 9.3 规模与超参（起始值）

| 项 | 建议 |
|---|---|
| 样本量 | 500–3000 条高质量。**超过 5000 条反而过拟合话题** |
| 基座 | Qwen2.5-7B-Instruct（或 4B，单卡 24G 能跑） |
| LoRA | r=16, alpha=32, dropout=0.05 |
| lr | 1e-4 → 5e-5（小数据集低一点） |
| epoch | 2–3，看 valid loss 拐点 |
| 评测 | 同一套 40 条盲测 + 风格指标（句长分布、emoji 率、连发条数、高频词重合） |

### 9.4 部署之后

微调模型上线要 GPU（vLLM）或云托管 LoRA，成本远高于 API。
**所以先论证收益**：如果盲测只从 65% 涨到 72%，不值得为它养一台显卡机器；那 7 个点用提示词再调两周通常也能拿到。

---

## 10. 部署

```
        ┌──────────── Caddy（443，自动 HTTPS） ────────────┐
        │  /c/<token> → 静态页 + Cookie                    │
        │  /me        → 口令 Cookie                        │
        └────────────────────┬────────────────────────────┘
                             ▼
        systemd: uvicorn app.main:create_app --factory --workers 1 --host 127.0.0.1
                ├─ FastAPI（API + 静态）
                ├─ APScheduler（30s，tz=Asia/Shanghai）
                └─ SQLAlchemy ──► data/app.db（WAL）
                             │
                             └─► api.deepseek.com
```

1 核 1G 够用（常驻 ~150MB）。连接串带 `journal_mode=WAL&busy_timeout=5000&foreign_keys=on`。
备份：每日 03:00 拷 `app.db` → 保留 7 天 → 每周同步到你电脑。

---

## 11. `/me` 后台

| 页 | 内容 |
|---|---|
| 消息流 | 按天分组、可搜索，每条标注 REPLY / PROACTIVE |
| 记忆库 | 四类记忆 + 私密区，表格编辑，改完热加载 |
| 发送日志 | 每次 tick 的 task × 原因码，一眼看出"今天为什么没发午饭" |
| 日报 | 今天聊几句、情绪走向、异常、明天该提醒你的事 |

---

## 12. 里程碑

| 阶段 | 交付 | 涉及 | 预计 |
|---|---|---|---|
| **M0** | 骨架：`uv run uvicorn` 起得来，静态页能开，建表，bootstrap 复制模板 | `pyproject` `main.py` `bootstrap.py` `db/` | 半天 |
| **M1** | 能聊（G1 + G2 骨架） | `api/chat.py` `core/*` `llm/client.py` | 2 天 |
| **M2** | 记得住且不泄漏（G3） | `core/memory.py` `core/situation.py` `test_isolation.py` | 1 天 |
| **M3** | 午饭一条（G4） | `messenger/*` `test_gate.py` | 1 天 |
| **M4** | 兜底（G5） | `core/guard.py` `test_guard.py` | 半天 |
| **M5** | 后台 + 日报（G6） | `api/admin.py` `web/admin.*` `notify/owner.py` | 1 天 |
| **M6** | 导入工具（G7） | `scripts/import_chat.py` | 1 天 |
| **M7** | 部署（Caddy / systemd / 域名） | 运维 | 半天 |
| **M8** | 数据集导出（G8）· 微调（P3） | `scripts/export_dataset.py` `finetune/` | 视情况 |

**M1 之前必须先有**：`persona/interview.md` 填完 + `fewshot.md` 有 60 条。否则 M1 的验收（盲测 60%）无从谈起。

---

## 13. 四个必须提前知道的坑

**① 绝对不能用多 worker。**
`uvicorn --workers 4` 会让 APScheduler 启动 4 份，同一条午饭发 4 次。
对策：`--workers 1` + 写库前查幂等键（唯一索引兜底）双保险。

**② 网站的"主动消息"到达率是最大产品风险。**
她没开页面，12:00 那条就只躺在数据库里。要弹到锁屏只能靠 Web Push：
- Android Chrome：装上 PWA 即可，稳。
- **iOS：必须先"添加到主屏幕"（16.4+）才支持推送**，权限提示挑时机。
- 所以 **P1 只做未读红点 + 第一屏引导装主屏，P2 才接 pywebpush**。

**③ 提示词预算会随人格文件膨胀。**
`style-rules.md` + `fewshot.md` 很容易写到 8k token。对策：few-shot 用**检索式少样本**（按场景取 6 条，不全塞），`prompt_version` 哈希便于回归，`usage.py` 超阈值告警。

**④ "装傻"和"诚实"必须是两条代码路径。**
装傻只作用于**记忆不确定**；身份问题按普通对话处理，提示词要求如实回答。记录范围仍由固定文案说明，不应承诺尚未实现的数据操作。

---

## 14. 开源清单（M7 之后）

- [ ] `LICENSE` = Apache-2.0；README 顶部一句话说明这是什么
- [ ] `persona-example/`、`memory-example/`、`config/*.example.*` 齐备，clone 即可跑 demo
- [ ] `.gitignore` 覆盖 `data/` `persona/` `memory/` `finetune/data/` `config/messaging.json` `.env`
- [ ] `git log --stat | grep -E "persona/|memory/|data/|finetune/data/"` 为空
- [ ] README 写明：本仓库不含任何真实对话、个人信息或训练集
- [ ] 危机词表抽成配置，别把"踩过的坑"写成注释
- [ ] `SECURITY.md`：说明这是私人陪伴工具，**不是心理健康服务**
- [ ] CI 只装 `dev`，验证 `import app` 不会拉 torch
