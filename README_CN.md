# SeekingContext

[English](README.md) / [中文](README_CN.md)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP](https://img.shields.io/badge/Protocol-MCP-green.svg)](https://modelcontextprotocol.io/)

**通用记忆 MCP 服务器**

每一条记忆都是可阅读的 `.md` 文件，能 `grep`、能 `git track`、能手动编辑——同时底层仍然提供亚秒级混合搜索。

---

## TL;DR

```bash
pip install seeking-context && seeking-context
```

**一行命令，零配置，无限上下文。**

| 特性 | 核心价值 |
|------|----------|
| 🪶 **轻量设计** | 无需 API Key、无需外部数据库，纯 Python + 内置嵌入模型 |
| 📄 **Markdown 即真相** | 每条记忆都是 `.md` 文件 —— 可 grep、可 git 追踪、可手动编辑 |
| 🔄 **跨 Agent 持久化** | 命名空间隔离，Claude Code、openclaw 等多框架共享同一实例 |
| 🔌 **多协议支持** | MCP (stdio/SSE)、REST API、Python SDK —— 任选接口 |
| 🧩 **原生集成** | 一键配置 Claude Code、openclaw、OpenViking、less-agent |
| ⚡ **零配置启动** | 装上即用，所有默认值开箱可用 |

**核心承诺**：删掉索引，运行 `seeking-context rebuild`，一切从 `.md` 文件恢复。你的记忆真正属于你。

---

## 为什么选择 SeekingContext？

大多数 Agent 记忆系统把数据锁在不透明的二进制数据库里。你看不了、搜不了、不能用 git 跟踪变更、不能用编辑器修一条坏记忆。

SeekingContext 走了一条不同的路：**你的记忆就是 Markdown 文件**。向量索引和全文索引是从这些文件派生出来的缓存，随时可以删掉重建。

```
~/.seeking_context/
├── memories/                     # 真相之源（人类可读）
│   ├── claude-code/
│   │   ├── .abstract.md          # 自动生成的目录摘要
│   │   ├── .overview.md          # 自动生成的概览表
│   │   ├── profile.md            # 只追加的用户画像
│   │   ├── entities/
│   │   │   └── mem_a1b2c3.md     # 一条记忆一个文件
│   │   └── preferences/
│   │       └── mem_d4e5f6.md
│   └── less-agent/
│       └── ...
├── chroma/                       # 派生向量索引（可重建）
└── metadata.db                   # 派生全文索引（可重建）
```

**删掉 `chroma/` 和 `metadata.db`，运行 `seeking-context rebuild`，一切恢复如初。** 这就是我们的承诺。

---

## 零配置启动

**一句话：装上就能用，无需任何配置。**

SeekingContext 开箱即用，所有默认值都经过精心设计：

- ✅ **无需 API 密钥** - 内置 `all-MiniLM-L6-v2` 嵌入模型
- ✅ **无需数据库配置** - SQLite + ChromaDB 自动初始化
- ✅ **无需配置文件** - 所有默认值开箱即用
- ✅ **一行安装** - `pip install seeking-context`
- ✅ **一行启动** - `seeking-context` 或 `seeking-context-api`

**快速启动：**
```bash
# 安装
pip install seeking-context

# 启动 MCP 服务器
seeking-context

# 或启动 REST API
seeking-context-api
```

真的就这么简单。配置是可选的——只有当你有特殊需求时才需要调整。

---

## 核心特性

### 双层存储架构

这是 SeekingContext 的核心设计理念：

- **第一层 — Markdown 真相之源**：每条记忆是一个 YAML frontmatter 的 `.md` 文件。人类可读、git 可追踪、grep 可搜索、手动可编辑。你以最通用的格式掌控自己的数据。
- **第二层 — 派生搜索索引**：ChromaDB（向量）和 SQLite/FTS5（关键词）是加速层，随时可从 Markdown 重建。它们是缓存，不是真相。

每次写入先落 `.md` 文件，再写索引。每次读取先查 `.md` 文件，找不到再查 SQLite。索引可以一条命令删掉重建。

### 智能搜索流水线

不是单纯的关键词匹配，也不是单纯的向量嵌入——而是四阶段流水线：

1. **混合搜索** — 向量语义相似度（70%）+ BM25 关键词匹配（30%），权重可调
2. **时间衰减** — 可配半衰期的指数衰减，近期记忆自动提升
3. **MMR 重排** — 最大边际相关性去除冗余结果，平衡相关性与多样性
4. **多粒度返回** — 每次查询可选 L0（摘要）、L1（概览）、L2（全文）

### 自动生成目录摘要

每次写入后，SeekingContext 自动生成：

- **`.abstract.md`**（每个目录）— 快速统计和最新条目
- **`.overview.md`**（每个命名空间）— 所有类别的 Markdown 表格，含数量统计

这些文件让你（或另一个 Agent）无需遍历每个文件就能快速了解记忆库的全貌。

### 其他能力

- **作用域隔离** — user / agent / session 三级作用域
- **命名空间隔离** — 多框架共享一个实例，ID 绝不冲突
- **多协议支持** — MCP（stdio/SSE/streamable-http）、REST API、Python SDK
- **Profile 只追加** — `profile` 类别只追加不覆盖，保留完整历史
- **六大记忆类别** — profile、preferences、entities、events、cases、patterns
- **CLI 工具** — 一键生成 Claude Code、less-agent、OpenViking、openclaw 配置

---

## 安装

```bash
pip install seeking-context
```

---

## 快速开始

### Python SDK

```python
from seeking_context import SeekingContextClient

client = SeekingContextClient()

# 存储记忆
client.add(
    content="用户偏好：Python 和 FastAPI",
    category="preferences"
)

# 搜索记忆
results = client.search("编程偏好", top_k=5)
```

### MCP 协议

配置 `.mcp.json`：

```json
{
  "mcpServers": {
    "seeking-context": {
      "command": "uv",
      "args": ["run", "seeking-context"]
    }
  }
}
```

使用 MCP 工具：

```python
# 存储
await memory_add(
    content="用户姓名：Alice",
    category="profile",
    user_id="alice"
)

# 搜索
results = await memory_search(
    query="用户信息",
    top_k=5
)

# 从 Markdown 重建索引（手动编辑 .md 文件后使用）
await memory_rebuild_index()
```

### REST API

```bash
# 启动服务
seeking-context-api

# 搜索记忆
curl -X POST http://localhost:9377/v1/memories/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Python", "top_k": 5}'
```

---

## Markdown 存储格式

每条记忆是一个带 YAML frontmatter 的 `.md` 文件：

```markdown
---
id: "a1b2c3d4-..."
category: entities
user_id: "claude-code:default"
agent_id: "claude-code:default"
created_at: "2026-03-15T10:30:00+00:00"
updated_at: "2026-03-15T10:30:00+00:00"
active_count: 3
metadata:
  source: claude-code-auto
---

# Abstract

用户偏好使用 uv 而非 pip 管理 Python 依赖。

# Overview

用户明确表示偏好使用 uv 作为 Python 包管理器。
所有项目应使用 `uv init`、`uv add`、`uv run`。

# Content

在 2026-03-15 的会话中，用户说"永远用 uv，
不要 pip"。这适用于所有 Python 项目。
```

你可以直接用编辑器修改这个文件，然后运行 `seeking-context rebuild` 同步索引。

---

## CLI 命令

### 服务器

```bash
seeking-context run           # 启动 MCP 服务器（stdio）
seeking-context run --all     # MCP（SSE）+ REST API 组合模式
```

### Markdown 管理

```bash
# 从 .md 文件重建向量 + 全文索引
# （证明 Markdown 是真相之源）
seeking-context rebuild

# 将现有 SQLite 数据导出为 .md 文件
# （已有数据的一次性迁移）
seeking-context export-markdown
```

### 框架配置生成

```bash
seeking-context setup claude-code [--write] [--plugin]
seeking-context setup less-agent [--write]
seeking-context setup openviking [--write]
seeking-context setup openclaw
seeking-context setup rest
```

---

## 核心概念

### 多粒度存储

每条记忆支持三种粒度：

```python
client.add(
    content="完整内容...",
    abstract="一句话摘要",      # 快速识别
    overview="结构化概览"       # 决策参考
)

# 指定返回粒度
results = client.search("查询", level=0)  # 只返回摘要
results = client.search("查询", level=1)  # 返回概览
results = client.search("查询", level=2)  # 返回完整内容
```

### 六大记忆类别

| 类别 | 用途 |
|------|------|
| `profile` | 用户画像（只追加） |
| `preferences` | 用户偏好 |
| `entities` | 命名实体 |
| `events` | 事件记录 |
| `cases` | 具体案例 |
| `patterns` | 可复用模式 |

### 命名空间隔离

多个框架共享同一实例：

```python
# 框架 A
client_a = SeekingContextClient(namespace="framework-a")

# 框架 B
client_b = SeekingContextClient(namespace="framework-b")

# 相同 user_id 不会冲突
client_a.add("记忆 A", user_id="alice")
client_b.add("记忆 B", user_id="alice")
```

跨命名空间搜索：

```python
results = await memory_search_cross(
    query="Python",
    namespaces=["framework-a", "framework-b"],
    top_k=10
)
```

---

## 混合搜索算法

```python
# 混合评分
combined_score = (
    vector_weight * vector_score +   # 默认 0.7
    text_weight * text_score         # 默认 0.3
)

# 时间衰减
decay_factor = 2 ** (-age_days / half_life_days)

# 近期提升
if age_days < boost_recent_days:
    decay_factor *= boost_factor

# MMR 重排序
mmr_score = (
    lambda * relevance -
    (1 - lambda) * max_similarity_to_selected
)
```

---

## 运行模式

| 模式 | 命令 | 协议 | 用途 |
|------|------|------|------|
| MCP-only | `seeking-context` | stdio/SSE/streamable-http | MCP 客户端（Claude Code、Cursor） |
| REST-only | `seeking-context-api` | HTTP | HTTP 客户端、跨语言 |
| Combined | `seeking-context run --all` | SSE + HTTP | 同时支持 MCP 和 REST |

---

## 配置

环境变量（前缀 `SEEKING_CONTEXT_`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_DIR` | `~/.seeking_context` | 数据目录 |
| `MARKDOWN_ENABLED` | `true` | 启用 Markdown 真相之源存储 |
| `VECTOR_WEIGHT` | `0.7` | 向量搜索权重 |
| `TEXT_WEIGHT` | `0.3` | 关键词搜索权重 |
| `TEMPORAL_DECAY_HALF_LIFE_DAYS` | `30.0` | 时间衰减半衰期 |
| `BOOST_RECENT_DAYS` | `7.0` | 近期提升天数 |
| `BOOST_FACTOR` | `1.2` | 近期提升因子 |
| `REST_HOST` | `127.0.0.1` | REST API 主机 |
| `REST_PORT` | `9377` | REST API 端口 |
| `API_KEY` | `None` | API 密钥（可选） |

设置 `SEEKING_CONTEXT_MARKDOWN_ENABLED=false` 可禁用 Markdown 存储，仅使用 ChromaDB + SQLite（向后兼容）。

---

## 存储架构

```
写入路径:  memory_add() → .md 文件 → ChromaDB + SQLite
读取路径:  memory_get() → .md 文件（兜底: SQLite）
重建:      seeking-context rebuild → 遍历 .md → 重新填充索引
```

- **Markdown**（`memories/`）：真相之源。YAML frontmatter + 分段正文。
- **ChromaDB**（`chroma/`）：派生向量索引（`all-MiniLM-L6-v2` 嵌入）。可重建。
- **SQLite**（`metadata.db`）：派生元数据 + FTS5 全文索引。可重建。

数据位置：`~/.seeking_context/`

---

## 开发

```bash
# 克隆
git clone https://github.com/yourusername/SeekingContext.git
cd SeekingContext

# 设置
uv venv .venv --python=3.12
source .venv/bin/activate
uv sync

# 测试
uv run pytest

# 覆盖率
uv run pytest --cov=seeking_context
```

---

## 路线图

- [x] MCP 协议支持
- [x] REST API
- [x] Python SDK
- [x] 命名空间隔离
- [x] CLI 工具
- [x] Markdown-first 存储（真相之源）
- [x] 自动生成目录摘要
- [x] 从 Markdown 重建索引
- [x] 数据库到 Markdown 迁移
- [ ] 更多向量数据库（Pinecone, Weaviate）
- [ ] Web UI
- [ ] 多租户架构
- [ ] 自定义嵌入模型
- [ ] 记忆质量评分

---

## 许可证

MIT License

---

## 联系方式

- **作者**: less
- **Email**: 3038880699@qq.com
- **GitHub**: https://github.com/yourusername/SeekingContext

---

## 致谢

本项目灵感来源于以下优秀项目：

**记忆管理框架：**
- [OpenViking](https://github.com/volcengine/OpenViking) - Context Database for AI Agents
- [mem0](https://github.com/mem0ai/mem0) - The Memory Layer for Personalized AI
- [mem9](https://github.com/mem0ai/mem9) - Memory management for AI applications

**Agent 框架：**
- [openclaw](https://docs.mem0.ai/integrations/openclaw) - AI agent framework with memory integration

**MCP 生态：**
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) - Model Context Protocol implementation
- [Claude Code Plugins](https://github.com/anthropics/claude-code) - MCP client integration examples

**技术支持：**
- [ChromaDB](https://www.trychroma.com/) - 向量数据库
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Web 框架
- [Pydantic](https://docs.pydantic.dev/) - 数据验证

---

**如果这个项目对你有帮助，请给一个 Star！**
