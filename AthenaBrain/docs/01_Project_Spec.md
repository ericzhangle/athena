## Project Spec（v0.1 摘要与落地约束）

### 来源
- `docs/ATHENA_BRAIN_PROJECT_SPEC_v0.1.txt`（由 `ATHENA_BRAIN_PROJECT_SPEC_v0.1.docx` 转写）

---

## 1. 项目目标（Goal）
- Athena Brain **不是**另一个大语言模型。
- Athena Brain 是一个**实验性认知架构**：验证 AI 能否在其生命周期中通过经历逐步增长认知。
- LLM 仅作为**语言接口**；“真正的智能”应当从**经历 → 概念 → 关系** 的持续生长中涌现。

## 1.1 Phase-1 的核心假设（BabyBrain）
- **Phase-1 只验证一件事**：概念能否从证据中逐步涌现并成熟。
- Phase-1 不追求更强 benchmark，不追求“像百科一样全知”；避免任何分散注意力的实现。

## 2. 三个核心对象（必须先定）
- **Experience**：一次真实互动事件的不可变记录（Athena 的“人生”）。
- **Concept**：从多次 Experience 中涌现并持续演化的概念单元（含成熟度/置信度/属性/示例等）。
- **Relation**：连接概念的关系（有类型、置信度与证据）。

## 2.1 Vision 与 Cognition 的分离（设计决策）
- Phase-1 不自研视觉模型。
- 视觉被视为“眼睛”，认知被视为“大脑”，二者是不同问题：
  - **Vision Interface**：使用成熟开源视觉模型生成 **Raw Observation / Perception**（特征与描述）
  - **Athena Cognition**：通过交互与证据累积形成 Experience、Concept 与 Relation
- 视觉输出必须被当作“观察”，而不是直接注入为“知识/概念结论”。

## 3. 提交（Commit）纪律
- 新信息不应直接成为知识。
- 推荐流水线：Experience → Working Memory → Short Memory → Sleep → Concept → Long-term Memory
- “知识必须挣来”（需要证据与巩固），并允许**遗忘/降置信度/冲突检测**。

## 3.1 “不要背 Wikipedia” 的可操作定义
这句话的真实含义是：

> **知识必须来源于证据，而不是复制百科定义。**

- 允许外部知识作为“可验证线索”，但必须：
  - 标注来源类别与优先级
  - 赋予更低初始置信度
  - 通过后续经历验证/修正

## 3.2 证据优先级（Evidence Priority）
- **Priority 1**：直接经历（最高置信度）
- **Priority 2**：重复观察/重复确认（置信度随次数增长）
- **Priority 3**：已验证的外部知识（可加速学习，但不能自动为真）
- **Priority 4**：生成的假设（最低置信度，必须验证）

## 4. Sleep Engine（核心创新之一）
睡眠不是空闲时间，而是认知活动。典型任务：
- 回放当天经历、去重、合并重复观察
- 冲突检测与标注
- 置信度增减
- 生成抽象与新概念
- 生成问题（驱动好奇心）
- 压缩记忆、更新概念图

## 5. 版本路线（Roadmap）
- v0.2：Experience Database
- v0.3：Concept Graph
- v0.4：Sleep Engine
- v0.5：Curiosity Engine
- v0.6：Growing Brain Prototype
- v1.0：Self-growing Cognitive Architecture

