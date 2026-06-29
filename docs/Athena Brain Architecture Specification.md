## Athena Brain Architecture Specification

### 元信息
- **版本**: v0.1（骨架）
- **定位**: 工程/实验实现的“怎么做”规格书（模块、接口、数据结构、实现方案）
- **与白皮书关系**: `Athena Brain White Paper.md` 解释为什么；本文件约束怎么落地

---

## 0. 术语表（必须统一）
- **Experience（经历）**：一次可追溯的输入-上下文-反馈事件（例如一轮对话、一段观察、一次行动及其结果）。
- **Concept（概念）**：可生长的知识单元，带证据与关系，可抽象、可修正。
- **Concept Graph（概念图）**：Concept 节点 + 关系边 + 证据引用 + 置信度/时间维度。
- **Sleep（睡眠整理）**：离线巩固过程（合并、抽象、压缩、纠错、索引重建）。

## 1. 系统边界与非目标（Non-goals）
- **非目标**：训练一个更大的通用 LLM。
- **边界**：LLM 作为语言接口与推理“工具”；核心资产是可解释、可演化的认知结构。

## 2. 顶层模块与职责
### 2.1 Language Interface（语言接口）
- **输入**：用户文本、系统提示、工具输出
- **输出**：结构化语义（候选 Concept/关系/意图）、自然语言回复
- **依赖**：Working Memory、Reasoning Engine

### 2.2 Working Memory（工作记忆）
- **职责**：当前任务状态、注意力焦点、短期上下文窗口管理

### 2.3 Short-term Memory（短期记忆）
- **职责**：保存近期 Experience，供睡眠整理与即时检索
- **策略**：时间衰减、任务相关性、容量上限

### 2.4 Long-term Memory（长期记忆）
- **职责**：稳定的 Experience 索引与可检索证据库（原始证据不丢）

### 2.5 Concept Graph（概念网络）
- **职责**：Concept 与关系的权威存储；支持抽象、修正、冲突管理、版本化

### 2.6 Reasoning Engine（推理引擎）
- **职责**：将“目标/问题”转为可执行推理计划（检索、图推理、工具调用、LLM 推理）

### 2.7 Sleep Engine（睡眠整理）
- **职责**：离线巩固：合并重复概念、形成抽象层、修复矛盾、重算置信度、重建索引

### 2.8 Curiosity Engine（主动探索）
- **职责**：发现知识缺口、生成可验证问题、驱动数据采集/对话探索

### 2.9 Planning Engine（规划系统）
- **职责**：长期目标分解、子目标生成、行动序列与资源预算

## 3. 核心数据结构（草案）
### 3.1 Experience
- `experience_id`
- `timestamp`
- `context_ref`（对话轮次/观察源/外部文件/网页等引用）
- `input` / `feedback` / `outcome`
- `proposed_concepts[]`
- `proposed_relations[]`
- `tags[]`（任务、领域、重要性）

### 3.2 Concept
- `concept_id`
- `name`
- `description`
- `created_at` / `updated_at`
- `evidence_refs[]`（Experience 引用）
- `confidence`
- `modalities`（text/image/audio/...）
- `aliases[]`
- `constraints[]`（适用范围、前提）

### 3.3 Relation
- `relation_id`
- `type`（is-a / part-of / causes / similar-to / contradicts / ...）
- `from_concept_id` -> `to_concept_id`
- `evidence_refs[]`
- `confidence`
- `valid_from` / `valid_to`（可选：时间有效性）

## 4. 关键接口（模块间契约）
> 本节写“请求/响应结构、错误码、幂等性、版本策略”。实现语言可后定，但接口先定。

- `ingest_experience(experience) -> ingest_result`
- `propose_concepts(experience, context) -> concept_candidates`
- `commit_concepts(concepts, relations, evidence) -> commit_result`
- `retrieve(query, context) -> evidence + concept_subgraph`
- `sleep_consolidate(window, budget) -> consolidation_report`

## 5. 学习闭环的最小可行实现（MVP）
- **MVP-1（BabyBrain）**：纯文本对话 + Experience 记录 + Concept Graph（增量写入）+ 基础检索
- **MVP-2**：加入 Sleep Engine（合并/去重/抽象的离线任务）
- **MVP-3**：加入 Curiosity Engine（提出可验证问题，驱动数据补全）

## 6. 评估与指标（必须工程化）
- **持续成长**：新概念学习曲线、遗忘率、迁移成功率
- **抽象能力**：层级概念质量、压缩比、泛化到新任务
- **修正能力**：矛盾发现率、纠错延迟、错误回滚能力
- **创造力/发现**：提出“可验证新假设”的数量与命中率
- **可解释性**：答案可追溯到哪些 Experience/Concept/Relation

## 7. 风险与约束
- **概念爆炸**：图规模失控、检索退化
- **错误固化**：低质量证据导致长期偏差
- **对齐与安全**：记忆污染、提示注入、隐私泄漏

## 8. 实现占位（后续补齐）
- 存储选型：SQLite/Neo4j/Graph DB/向量库（取舍理由）
- 索引：向量索引 + 图索引 + 证据索引
- 版本化：Concept/Relation 的演化历史与可回滚


