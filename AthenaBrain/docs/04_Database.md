## Database Spec（Experience / 存储 / 索引）

> 本文件聚焦“经历如何落盘、如何引用、如何检索”，为 Phase 1 Apple Test 提供可追溯基础。

### 现状
`ATHENA_BRAIN_PROJECT_SPEC_v0.1` 已给出 Experience 字段草案，并强调 **Experience immutable**。

---

## 1. Experience（不可变记录）
### 1.1 最小字段集（建议）
- `experience_id`
- `timestamp`
- `source`（user / system / tool）
- `modalities`（text/image/audio）
- `raw_inputs`（原始对话/图片引用/工具输出引用）
- `perception_refs[]`（可选：指向 Perception 的引用，见下）
- `athena_outputs`（当时的回复、当时提出的问题）
- `user_feedback`（纠正/确认/评分）
- `tags`
- `processed_flag`（是否已进入睡眠巩固）

### 1.2 不可变的含义
- 任何“纠错”都新增 Experience（或新增 correction 事件），而不是改写旧记录。

## 2. 引用规则（Evidence Ref）
- Concept/Relation 必须通过 `evidence_refs[]` 指向一个或多个 Experience。
- 引用应支持：定位到对话轮次、图片文件、或工具输出。

## 2.1 Belief Revision / Evidence Trust（证据修正）
Athena 不应在一开始就为所有来源建立复杂 trust weighting。更接近人类学习的方式是：

> 先把来源信息作为临时可信证据保存；当后续观察、反馈或参照知识出现冲突时，再修正证据状态。

### 核心对象
- **Evidence**：任何可以支撑认知的证据单元，例如用户陈述、图片感知、外部参照、模型输出。
- **Claim**：证据提出的可验证陈述，例如 `Apple is-a Fruit`、`Image X shows Apple`。
- **ValidationEvent**：证据状态变化的记录，例如确认、质疑、撤销、污染。
- **SourceProfile**：来源历史表现的轻量记录；Phase 1 不做复杂评分，只记录来源与历史事件。

### EvidenceStatus
- `provisional`：临时相信，允许进入概念形成，但不能视为绝对真理。
- `confirmed`：被后续证据支持。
- `disputed`：存在冲突，需要验证。
- `invalidated`：该证据被撤销，不能继续支撑概念成熟。
- `contaminated`：来源或样本存在问题（例如图片被告知有问题），其下游感知也应谨慎使用。

### 原则
- 用户、图片、百科、模型输出都不是天然真理；它们都是 Evidence。
- 图片感知可作为强证据，但如果用户指出图片有问题，该图片相关 Evidence 应被标记为 `invalidated` 或 `contaminated`。
- Wikipedia/reference 可作为参照证据，用于验证与冲突检测，但不自动覆盖直接经历。

## 2.1 Perception（感知记录：可选但建议预留）
> Perception 用来承载“看见了什么特征”，避免视觉模型直接注入“这是什么”的语义结论。

### 最小字段集（建议）
- `perception_id`
- `timestamp`
- `source_model`（例如 CLIP/SigLIP/Qwen-VL/LLaVA 等）
- `input_ref`（图片文件/帧/区域）
- `features`（结构化特征：颜色/形状/纹理/局部结构/尺寸估计等）
- `confidence`（特征级/整体）

### 约束
- Perception 不应包含“苹果/狗”等语义标签作为确定知识；若包含，只能当作**假设**，并带低置信度与来源标注。

## 3. 检索需求（Phase 1）
- 按概念名/别名检索相关 Experience
- 按最近/置信度/成熟度筛选
- 按“图片特征摘要”检索（可先占位，后续实现）

## 4. Memory（记忆层：组织与索引，占位）
> Phase-1 可用最简单实现（例如：把 Experience 放入短期集合 + 索引），但术语与边界要先定。

- **Working Memory**：当前任务/对话焦点（易变）
- **Short-term Memory**：近期经历集合（等待巩固）
- **Long-term Memory**：稳定概念与可追溯证据索引（不等于删原始经历）

