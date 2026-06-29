## Architecture（模块、接口与最小闭环）

### 现有规格书
- 旧版汇总：`docs/Athena Brain Architecture Specification.md`
- 建议后续把旧版内容逐步迁移/拆分到本目录编号文档中，避免单文件膨胀。

---

## 1. 最小闭环（MVP = Phase 1 Apple Test）
本项目的第一阶段最小闭环以 `02_Cognitive_Spec.md` 的 **Apple Test** 为验收标准：

- Experience 必须可记录、可引用
- Concept/Relation 必须可生成、可更新、可追溯到证据
- 语言输出必须体现“从经历中长出来”，而非百科背诵

## 1.1 认知管线（建议用词：认知科学视角）
> Phase-1 不需要实现 Theory，但需要在架构中预留“通向 Theory”的成长路径。

观察世界（Raw Observation）
↓
感知世界（Perception：特征化、结构化，但不下语义结论）
↓
积累经历（Experience：带上下文与交互）
↓
形成记忆（Memory：组织、索引、可检索）
↓
抽象概念（Concept：从多次经历中涌现）
↓
构建理论（Theory：跨概念的分类/因果/规律与假设，长期目标）
↓
修正理论（用新证据不断修正）
↓
再观察世界（闭环）

## 1.2 State-based Intelligence（状态驱动智能）
`Athena Brain.docx` 的核心主张是：**智能主要由“认知状态的持续演化 + 状态迁移规则”构成**，而不是由一次性训练后的参数静态存储知识构成。

### External State（外部状态：世界状态）
外部状态描述“世界此刻是什么样”：
- 当前看到什么 / 听到什么
- 当前正在和谁对话
- 当前有哪些图片/输入材料
- 当前有哪些任务/环境约束

### Internal State（内部状态：心智状态）
内部状态描述“Athena 此刻在想什么/在修正什么”，它应该成为长期的主要驱动力：
- 当前关注什么（Attention）
- 当前有哪些未解决的问题（Curiosity）
- 当前有哪些 Concept 正在形成/成熟
- 当前有哪些 Mental Model 正在修正（预测失败/冲突触发）
- 当前 Sleep Engine 是否正在整理
- 当前 Identity 偏向哪些领域（兴趣、目标、进度）
- 当前哪些证据存在冲突（Conflict Set）

> **长期核心假设**：真正的 AGI 很可能主要由 Internal State 驱动，而不是由外部输入直接触发。外部输入只是“观察材料”，内部状态决定“下一步要问什么、要验证什么、要修正什么”。

## 2. 顶层模块（概念级）
- Language Interface（语言接口）
- Vision Interface（视觉接口/“眼睛”）
- Perception（感知：从观察到特征）
- State Manager（状态管理：维护 External/Internal State 与迁移规则，占位）
- Working Memory（工作记忆）
- Short-term Memory（短期记忆）
- Long-term Memory（长期记忆）
- Experience Database（经历数据库）
- Concept Graph（概念网络）
- Reasoning Engine（推理引擎）
- Sleep Engine（睡眠整理）
- Curiosity Engine（主动探索）
- Planning Engine（规划系统）
- Theory Layer（理论层：长期目标，占位）

## 3. 接口（先定契约，后做实现）
> 这里先列“必须存在”的接口名与职责；具体字段在 `04_Database.md` 与 `06_Concept_Graph.md` 定。

- `perceive(observation) -> perception`（把 Raw Observation 转为结构化 Perception）
- `ingest_experience(experience)`
- `propose_concepts(experience, context)`
- `commit_concepts(concepts, relations, evidence)`
- `retrieve(query, context)`
- `sleep_consolidate(window, budget)`

