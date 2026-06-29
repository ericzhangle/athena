## Concept Graph（概念网络：节点、关系、版本与证据）

---

## 1. Concept（节点）
### 1.1 必备字段（Phase 1）
- `concept_id`
- `name`
- `description`（允许是“基于经历的草案”，不要硬凑百科）
- `attributes[]`（每条含：值、置信度、证据引用）
- `examples[]`（引用 Experience）
- `confidence`
- `maturity`
- `created_at` / `updated_at`

### 1.2 证据优先级（影响置信度）
- 直接经历 > 重复观察/确认 > 已验证外部知识 > 生成假设
- 图结构里应能区分“这条属性/关系来自哪类证据”，以便解释与纠错。

## 2. Relation（边）
### 2.1 关系类型（最小集合）
- `is-a`
- `part-of`
- `similar-to`
- `different-from`
- `contradicts`（用于显式记录冲突）

### 2.2 证据与置信度
每条关系必须有：
- `evidence_refs[]`
- `confidence`
- （可选）`valid_from/valid_to` 表示时间有效性或条件

## 3. 版本化与可回滚（建议）
- Concept/Relation 的每次更新应保留演化历史（event-sourcing 或版本快照）
- 支持“回看某一天 Athena 当时怎么理解苹果”

## 4. Theory（理论，占位）
> Theory 可以被表示为一种更高层的节点/结构（例如：分类规则、因果图、可检验假设集合），并用证据不断修正。
> Phase-1 不要求实现，但文档层面先把“从 Concept 走向 Theory”写清楚。

