# SAGT MVP 方案与任务拆解

> 版本：v1.2 ｜ 依据《SAGT 需求文档 v1.2》§19 范围 A 与《SAGT 技术架构设计 v1.2》
> 目标：单人 4~5 周（约 25~30 个有效工作日）交付**一条可完整演示的故事线**，八大技术点全部在场且被证明。
>
> v1.1 变更：批量任务/员工偏好记忆/功能级授权矩阵移出 MVP；M4 补冷启动引导与同字段提案合并；M5 Rerank 改 LLM listwise；M7 授权简化为角色级并补客户移交。
> v1.2 变更：意图 13 个（+knowledge_qa）；评测集对齐 500 条基线（种子金标 + LLM 扩写），四维 Judge 与工程目标值同步进 M9 与 DoD。
> v1.2 补充（2026-08）：M4 权限闸门细化为「权限中间件 + bypass 模式」（借鉴 AgentScope 2.0 权限设计）：工具调用统一过权限中间件，只读工具命中白名单 bypass 免确认，write 工具默认走 proposal/approval_token 确认流，bypass 白名单可配置、全程审计留痕。

---

## 1. MVP 的唯一验收标准：一条演示故事线

> 员工小张登录 sidebar → 点开客户"王女士"，看到 AI 提取的**画像卡**（偏好/需求/价值分层，每字段附依据）与**标签建议**（附理由，一键修正）→ 输入"帮我写个回访话术，重点是新款到货"→ Coach Agent **流式输出带引用的话术草稿** → 小张点"重新生成"并补充要求 → 采纳最终版 → 管理者在 admin 看到**会话监控与采纳记录** → 点开 **Monitor** 回放本次请求的完整决策链（意图→画像读取→RAG 检索→生成→提案）→ 命令行一键跑 **profile_eval / tag_eval / talk_eval**，输出准确率报告。

**走完这条线 = MVP 完成。** 任何不服务这条线的功能，MVP 阶段一律不做。

---

## 2. 范围矩阵（对照 PRD 范围划分）

### 2.1 MVP 包含

| 域 | 内容 | 说明 |
|---|---|---|
| 数据 | employee / customer / follow_up / purchase / customer_profile / tag_dict / customer_tag / suggestion / suggestion_action + AI 运行域表 | 约 16 张核心表；service_record、schedule_task、order(mock) 延后 |
| 画像 | Profile Agent：手动触发 + 新跟进记录触发增量；字段级提案-采纳 | 事件消费 MVP 用"落库后同步 HTTP 通知"简化，outbox+Stream 放 P2 |
| 标签 | Ops Agent 最小版：基于画像产出标签建议 + 采纳/修正 | 信号识别/日程不做 |
| 话术 | Coach Agent + playbook_kb / product_kb RAG + 采纳/修改/重新生成(≤2)/拒绝 | 相似客户不做 |
| 意图 | 13 个员工指令意图（含 knowledge_qa）；Rule + Embedding(内存样例库简化版) + LLM 三路 | 样例库先手工维护 5 条/意图 |
| HITL | proposal 机制 + 中断确认面板（确认/放弃/重新生成）+ 幂等 + 审批凭证 | LangGraph interrupt/checkpoint |
| 知识库 | 上传/切片/向量化/原子切换/检索测试 | playbook_kb 种子话术 ≥30 条、product_kb 商品 ≥10 |
| Monitor | Run 列表 + Span 基础下钻（简版瀑布） | 概览看板延后 |
| 评测 | CLI 跑 3 数据集（profile_eval/tag_eval/talk_eval）出报告 | 平台化延后 |
| admin | 员工管理(简) / 客户管理 / 会话监控(含采纳明细) | 报表、服务记录、订单页延后 |
| 部署 | compose：mysql+redis+business-mock+mcp-server+sagt-agent+frontend | Milvus 必含（RAG 是 MVP 核心）；lite profile 延后 |

### 2.2 明确出 MVP（→P2/ADV）

信号识别与日程（P2）、拜访准备组合任务（P2）、相似客户检索（ADV）、质量报表（P2）、技能管理页（ADV，MVP 期技能硬编码 2 个配置）、批量任务（ADV）、员工偏好记忆 mem_user（ADV）、功能级授权矩阵（P2，MVP 角色两级）、人工接管类能力（不需要）、outbox 事件总线（P2，MVP 用同步通知过渡）。

---

## 3. 数据基线（种子数据规格）

| 数据 | 规模 | 质量要求 |
|---|---|---|
| 员工 | 2（小张/小李）+ 1 管理者 | 客户分配各 10 人 |
| 客户 | 20 | 覆盖生命周期四阶段：新客 5 / 意向 7 / 老客 5 / 流失风险 3 |
| 跟进记录 | ~300（人均 15） | **必须预埋**：承诺类语句、异议语句、价格敏感表述、复购信号——画像与标签评测的金标来源 |
| 消费记录 | ~80 | 金额/品类分布合理，支撑价值分层 |
| 话术库 | ≥30 条（分场景：回访/促单/异议处理/挽回） | 供 RAG 命中与引用演示 |
| 商品 | 10（零售品类） | 含卖点与参数 |
| 人工标注 | 画像金标 20 客户 × 核心字段；标签金标 100 条；意图样例 100 条种子 | 评测集地基（共 500 条基线），**种子数据阶段就要产出**；扩写至 500 条在 M9 完成 |

---

## 4. 任务拆解（11 个里程碑）

> 估算为单人专注工作日；每里程碑有独立可验收产出，允许随时停下来演示当前进度。

### M0 工程地基（2 天）
| 任务 | 产出 | 验收 |
|---|---|---|
| Monorepo 骨架（frontend-web / business-mock / sagt-agent / mcp-server / deploy / docs） | 目录 + README + .gitignore | 各端 hello 可跑 |
| docker-compose（mysql+redis）+ 各服务 Dockerfile 占位 | compose.dev.yml | `docker compose up` 起 mysql/redis |
| 前端 Vite 双入口（admin/sidebar）+ 路由骨架 + 登录页 | 可登录空壳 | 登录跳转对应端 |

### M1 业务数据域（3 天）
| 任务 | 产出 | 验收 |
|---|---|---|
| Java：认证（JWT）+ employee/customer 域 CRUD + 客户归属切面 | REST API | Postman 通过；越权 403 |
| Java：follow_up / purchase 域 + Flyway 迁移 | REST API | CRUD 正常 |
| 种子数据脚本（§3 规格，含金标预埋） | seed SQL/JSON | 数据可一键灌入 |
| 前端：我的客户列表 + 客户详情骨架（跟进时间线/消费记录） | 页面 | 能看到种子数据 |

### M2 AI 运行时地基（3 天）
| 任务 | 产出 | 验收 |
|---|---|---|
| sagt-agent 骨架：FastAPI + LangGraph 主图 + SSE 通道 | /api/ai/chat 可流式回声 | curl SSE 正常 |
| LLM Gateway：chat/embedding 两端点 + 模型路由 + 重试/超时 + 成本记账 | gateway 模块 | 单测通过 |
| Trace 最小版：agent_run + agent_span 落库 | 表 + 埋点 | 一次请求可查 Run |
| Redis 会话上下文装载 | chat:ctx | 多轮对话上下文保持 |

### M3 意图分类（2 天）
| 任务 | 产出 | 验收 |
|---|---|---|
| 意图 Schema 表 + 13 意图定义（含 knowledge_qa）+ 每意图 5 条样例入库 | 配置数据 | Schema 管理接口可用 |
| Rule 分类器（菜单直达/关键词硬规则）+ LLM 分类器 + Embedding 简化版（内存余弦）+ 融合逻辑 | intent 模块 | 自测集 ≥85% L1 准确 |
| 路由接入主图 + routing_reason/confidence 落库 | — | Monitor 可见路由决策 |

### M4 画像 Agent（3 天）
| 任务 | 产出 | 验收 |
|---|---|---|
| mcp-server 骨架 + 只读工具 4 个（search_customers/get_customer_profile/list_follow_ups/list_purchases）+ 权限中间件（统一闸门 + bypass 白名单：只读工具 bypass 免确认，write 工具默认强制走 proposal 确认流） | MCP 服务 | 工具调用通、越权拒；write 工具绕过确认 100% 拒；bypass/确认均留审计 |
| Profile 子图：LLM 结构化抽取 + 字段级 diff + update_profile_field(write，interrupt) | 子图 | 产出字段更新提案 |
| HITL 通用机制：proposal 表 + approval_token + 幂等键 + confirm 接口 + 30min 过期任务 + 同字段提案合并 | 机制 | 无凭证 write 100% 拒 |
| 前端：画像卡（字段/依据/更新时间）+ 更新建议确认面板 + 新客空态展示首访采集清单（冷启动引导） | 页面 | 采纳后画像更新、修正留痕 |
| 触发链路：新跟进记录落库 → 同步通知 sagt-agent → 增量画像 | 链路 | 补录跟进后 30s 内出提案 |

### M5 话术 Agent + RAG（4 天，MVP 最重）
| 任务 | 产出 | 验收 |
|---|---|---|
| Milvus 接入 + knowledge_doc/chunk 表 + 上传/切片/向量化/原子切换 | 入库管线 | 文档 ready 可检索 |
| RAG 管线：rewrite → dense+sparse 各 top20 → RRF → LLM listwise rerank → 阈值 → 注入 | rag 模块 | 检索测试页可用 |
| playbook_kb / product_kb 种子内容灌入（话术 ≥30 条） | 数据 | 引用可命中 |
| Coach 子图：装配技能配置（硬编码 2 个）→ 读画像+跟进 → RAG → 生成 → 事实自检 | 子图 | 话术带引用、与画像无冲突 |
| 建议卡交互：采纳(可编辑)/重新生成(≤2,附要求)/拒绝(必填原因) + suggestion_action 落库 | 前端+接口 | 行为记录完整 |
| SSE 事件全量：intent/tool_call/rag_citation/token/proposal/done | 协议 | 前端渲染正确 |

### M6 标签能力（1.5 天）
| 任务 | 产出 | 验收 |
|---|---|---|
| tag_dict + save_tags(write) 工具 | — | 幂等+凭证生效 |
| Ops 最小子图：画像→标签建议（附依据）；画像更新后联动复核 | 子图 | 建议卡可采纳/修正 |
| 前端：标签建议卡 + 客户列表标签筛选 | 页面 | 修正即时生效并记录 |

### M7 admin MVP（2 天）
| 任务 | 产出 | 验收 |
|---|---|---|
| 员工管理（CRUD+客户分配+移交记审计事件）+ 角色级开关 | 页面+接口 | 授权即时生效 |
| 客户管理（全量档案视图） | 页面 | 管理者可查 |
| 会话监控：会话列表 + 逐轮详情（意图/Agent/引用/采纳状态） | 页面 | 可跳转 Monitor |

### M8 Monitor 简版（1.5 天）
| 任务 | 产出 | 验收 |
|---|---|---|
| Run 列表（筛选）+ Span 时间线（简版瀑布：展开输入输出摘要/tokens/耗时） | 页面 | 演示故事线第 6 步可走 |

### M9 评测 CLI（2 天）
| 任务 | 产出 | 验收 |
|---|---|---|
| eval_mode（禁写业务库/记忆）+ Runner 骨架 | — | 评测不污染线上 |
| 三数据集构造：profile_eval(金标对比)/tag_eval/talk_eval(四维 LLM-Judge：相关性/准确性/完整性/有用性) | eval-data | 种子金标可直接复用；LLM 扩写对齐 500 条基线（人工抽检） |
| 报告输出（指标+case 明细）+ 与基线 diff | CLI | 一键出报告 |

### M10 部署与打磨（2 天）
| 任务 | 产出 | 验收 |
|---|---|---|
| 全量 compose（含 Milvus）+ 健康检查 + 一键灌种子 | compose.full.yml | 冷启动 ≤5 分钟 |
| 演示脚本（账号/引导词/故障预案）+ README | docs | 陌生人可按脚本演完 |
| 异常场景最小集：LLM 超时降级、SSE 重连、提案过期、无凭证拒写 | — | §17 E1/E7/E8/E12 通过 |

**合计：约 26 个工作日（5 周余量，含缓冲）。**

---

## 5. 依赖关系与关键路径

```
M0 → M1 ─┬→ M4(画像) ─┬→ M6(标签)
         │            │
M0 → M2 → M3 ─────────┴→ M5(话术+RAG) → M8(Monitor) 
                                        ↘ M9(评测)
M1 → M7(admin)        M4..M9 → M10(部署打磨)
```

**关键路径 = M0→M2→M3→M5**（AI 运行时 → 意图 → 话术 RAG），占总量近半；M1 业务域与 M2 AI 地基可交叉推进。M5 是唯一"不可压缩"里程碑，若进度吃紧：先砍 M6 的联动复核、M7 的授权开关、M9 的基线 diff，**保住故事线六步**。

---

## 6. MVP 风险预案

| 风险 | 预案 |
|---|---|
| RAG 引用质量不稳（演示翻车点） | 话术库种子按"高区分度"编写；阈值与注入格式预调优；演示脚本选高置信 query |
| 画像 LLM 抽取不稳定 | 抽取用 JSON Schema 强约束 + 重试；演示客户预跑一遍，提案留档 |
| LLM API 波动 | Gateway 备用模型 + 降级话术；演示前预热 |
| Milvus 本机资源 | 单机 standalone 足够（向量 <10 万）；异常时重启恢复脚本备好 |
| 时间超支 | 按 §5 砍单顺序执行；任何 P2 功能请求一律记录进 backlog 不做 |

---

## 7. Definition of Done（MVP 总验收）

- [ ] 冷启动：`docker compose --profile full up` + 灌种子 ≤5 分钟，无手工步骤
- [ ] 演示故事线六步（§1）一次性走通，无控制台报错
- [ ] 画像字段覆盖率 ≥90%（对金标）；标签建议带依据率 100%
- [ ] 所有 write 操作无确认不生效；无凭证 write 拦截率 100%
- [ ] 每次 AI 交互 100% 产生可回放 Run
- [ ] 评测 CLI 三数据集一键出报告，指标达到 PRD v1.2 目标基线（意图 L1 ≥92% / RAG Recall@5 ≥90% / 工具成功率 ≥97% / 四维 Judge ≥4.3）；简历只写实测值
- [ ] README + 演示脚本 + 架构图三份文档齐备
