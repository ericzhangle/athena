## State Manager（External / Internal State 与状态迁移）

### 定位
`State Manager` 是 Athena Brain 从“响应式 AI”走向“内部状态驱动认知系统”的关键模块。

它不负责直接回答问题，也不负责直接生成概念；它负责维护 Athena 当前的**世界状态**与**心智状态**，并决定哪些观察值得进入注意力、哪些冲突应该触发好奇心、哪些问题应该被主动提出。

---

## 1. 核心假设
Athena Brain 的长期假设之一：

> 真正的成长型智能不只是被外部输入触发，而是由 Internal State 的持续演化驱动。

传统 LLM 通常是：

输入 → 推理 → 输出

Athena Brain 希望逐步走向：

外部观察 → 内部状态变化 → 好奇心/冲突/目标驱动 → 主动提问或行动 → 新观察 → 再次更新内部状态

因此，`State Manager` 的核心价值不是“保存上下文”，而是让 Athena 拥有一个可追踪、可修正、可持续演化的“当前心智状态”。

---

## 2. 状态分层

### 2.1 External State（外部状态）
External State 描述 Athena 当前面对的世界与任务环境。

它回答：

- Athena 当前看到了什么？
- Athena 当前听到了什么？
- Athena 正在和谁互动？
- 当前有哪些图片、文字、文件、工具输出？
- 当前任务是什么？
- 当前处在什么时间、场景、实验阶段？

External State 是“世界给 Athena 的材料”，但它本身不是智能。

### 2.2 Internal State（内部状态）
Internal State 描述 Athena 当前的认知活动。

它回答：

- Athena 当前关注什么？
- 哪些问题还没有解决？
- 哪些概念正在形成？
- 哪些证据之间存在冲突？
- 哪些心智模型正在被修正？
- Athena 当前的兴趣、目标和身份偏向是什么？
- Sleep Engine 是否正在整理，整理了什么？

Internal State 是 Athena 的“认知驱动层”。它决定 Athena 下一步应该问什么、记什么、怀疑什么、验证什么。

---

## 3. 最小状态对象（Phase 1）
Phase 1 不需要完整 AGI 状态系统，但必须先定义最小字段，以便 Apple Test 可以被记录、复现和评估。

### 3.1 `ExternalState`
最小字段建议：

```json
{
  "state_id": "external_state_001",
  "timestamp": "2026-06-29T00:00:00Z",
  "session_id": "phase1_apple_test_001",
  "current_user": "user",
  "current_task": "learn_apple_from_interaction",
  "visible_inputs": [
    {
      "input_id": "image_001",
      "type": "image",
      "path": "inputs/apple_001.jpg",
      "status": "available"
    }
  ],
  "conversation_context": [
    {
      "speaker": "user",
      "text": "苹果是一种水果。"
    }
  ],
  "environment_notes": []
}
```

### 3.2 `InternalState`
最小字段建议：

```json
{
  "state_id": "internal_state_001",
  "timestamp": "2026-06-29T00:00:00Z",
  "attention_focus": [
    {
      "target": "apple",
      "reason": "new_concept_introduced_by_user",
      "strength": 0.8
    }
  ],
  "pending_questions": [
    {
      "question": "苹果通常有什么颜色和形状？",
      "reason": "concept_attributes_unknown",
      "priority": 0.7,
      "status": "open"
    }
  ],
  "active_concepts": [
    {
      "name": "Apple",
      "status": "forming",
      "confidence": 0.3,
      "evidence_refs": []
    }
  ],
  "conflict_set": [],
  "curiosity_queue": [
    {
      "topic": "Fruit",
      "reason": "user_stated_apple_is_a_fruit_but_fruit_is_undefined",
      "priority": 0.8
    }
  ],
  "identity_focus": [
    "learn_from_evidence",
    "avoid_encyclopedia_copying",
    "ask_when_uncertain"
  ],
  "sleep_status": {
    "state": "idle",
    "last_run": null
  }
}
```

### 3.3 `StateTransitionEvent`
每一次状态变化都应该可记录。

```json
{
  "transition_id": "transition_001",
  "timestamp": "2026-06-29T00:00:00Z",
  "from_state": "external_state_001",
  "to_state": "internal_state_001",
  "trigger": "user_introduced_new_concept",
  "condition": "Athena does not have a mature Apple concept",
  "result": [
    "attention_focus_created",
    "pending_question_created",
    "active_concept_created"
  ],
  "evidence_refs": [
    "experience_pending_001"
  ]
}
```

---

## 4. 状态迁移规则（Phase 1）
状态迁移规则比字段本身更重要。字段只是记录，迁移规则决定 Athena 是否真的在“认知”。

### 4.1 Raw Observation → Perception
触发条件：

- 图片、文本、音频或工具输出进入 External State
- Vision Interface 或其他感知接口可提取结构化特征

结果：

- 生成 `Perception`
- 不直接生成 Concept
- 如果感知模型给出语义标签，只能作为低优先级假设

### 4.2 Perception → Attention
触发条件之一：

- 新奇：出现未见过的对象/词汇/特征
- 冲突：感知结果与已有 Concept 或 Mental Model 不一致
- 重要：用户明确指向或强调
- 好奇心：Internal State 中已有未解决问题相关
- 任务相关：当前实验或目标需要关注

结果：

- 更新 `attention_focus`
- 可能创建 `pending_questions`

### 4.3 Attention → Experience
触发条件：

- 出现有意义互动，例如用户命名、纠正、解释、上传示例
- Athena 主动提出问题，并收到用户反馈

结果：

- 生成不可变 `Experience`
- 将相关 Perception、对话、用户反馈写入证据链

### 4.4 Experience → Working Memory
触发条件：

- 当前互动尚未巩固
- 仍存在待解决问题或临时假设

结果：

- Experience 进入短期可检索范围
- 更新 `active_concepts`
- 更新 `pending_questions`

### 4.5 Working Memory → Long-term Memory
触发条件：

- Sleep Engine 运行
- Experience 被判定为有保留价值
- 与正在形成的 Concept/Relation 有关

结果：

- Experience 被长期索引
- 但原始 Experience 不被改写

### 4.6 Memory → Concept
触发条件：

- 有足够证据支持某个概念雏形
- 或用户明确命名并提供了至少一个可追溯例子

结果：

- 新建或更新 Concept
- 记录 confidence、maturity、evidence_refs
- 不确定部分保留为问题或低置信属性

### 4.7 Concept → Curiosity
触发条件：

- 概念属性缺失
- 概念边界不清
- 概念之间存在冲突
- 某个关系置信度过低

结果：

- 生成 `curiosity_queue`
- 生成可问用户的问题
- 生成可验证假设

### 4.8 Evidence → Belief Revision
触发条件：

- 新 Evidence 与已有 Concept/Relation 冲突
- 用户明确纠正前一条信息
- 用户指出图片、文本或来源有问题
- 外部参照知识与当前认知不一致

结果：

- 更新 Evidence 状态：`provisional` / `confirmed` / `disputed` / `invalidated` / `contaminated`
- 将相关 Concept/Relation 放入 `conflict_set`
- 生成需要验证的问题
- 如果关键证据被 `invalidated`，下游概念属性或关系不能继续依赖该证据成熟

示例：

用户先说：“这张图里的是苹果。”

后来用户说：“刚才那张图有问题，不应该作为苹果样本。”

Athena 应当：

- 将该图片 Perception 相关 Evidence 标记为 `invalidated` 或 `contaminated`
- 降低/撤销由该图片支持的属性
- 保留事件历史，而不是删除原始 Experience
- 生成问题：“哪些关于 Apple 的属性仍有有效证据支持？”

---

## 5. Internal State 驱动的典型例子

### 5.1 苹果例子（Phase 1）
用户说：

> 苹果是一种水果。

Athena 的 External State：

- 当前对话出现“苹果”和“水果”
- 用户做出分类陈述

Athena 的 Internal State：

- `Apple` 是新概念，进入 `active_concepts`
- `Fruit` 也是未成熟概念，进入 `curiosity_queue`
- 注意力聚焦到“苹果是什么”和“水果是什么”
- 生成问题：“你能给我看一个苹果吗？”、“水果是什么意思？”

这时 Athena 的提问不是为了闲聊，而是 Internal State 在驱动下一次观察。

### 5.2 鲸鱼例子（长期验证）
历史知识：

- 用户曾告诉 Athena：鲸鱼是动物
- Athena 已经有早期概念：鱼生活在水里
- Athena 又观察到：鲸鱼生活在水里

Internal State 可能产生冲突：

- `Whale is-a Animal`
- `Whale lives-in Water`
- `Fish lives-in Water`
- 但 `Whale is-not Fish` 或尚未明确

于是 Athena 主动提出：

> 昨天你告诉我鲸鱼是动物，但它为什么生活在水里却不是鱼？

这是项目长期要验证的现象：问题不是由用户刚刚输入直接触发，而是由 Internal State 中的冲突、概念边界和未解问题演化出来。

---

## 6. Phase 1 不做什么
为了保持 BabyBrain 原型纯粹，Phase 1 暂时不做：

- 不实现复杂情绪系统
- 不实现完整 Theory Layer
- 不实现多领域专家模块
- 不做大规模数据库优化
- 不追求百科知识覆盖
- 不让视觉模型直接注入“这是什么”的长期知识

Phase 1 只验证：

> External State + Perception + Experience + Internal State 是否能形成一个可追溯、可修正、非百科式的早期 Concept。

---

## 7. 验收标准（State Manager）
Phase 1 的 `State Manager` 通过标准：

- 能记录 External State（输入、图片、对话、任务）
- 能记录 Internal State（注意力、问题、活跃概念、冲突、好奇心）
- 能记录至少 3 类状态迁移：
  - Observation/Perception → Attention
  - Attention → Experience
  - Experience/Memory → Concept
- 能解释 Athena 为什么提出某个问题
- 能把问题追溯到 Internal State 中的未解概念、冲突或低置信证据
- 不把视觉模型输出直接当作长期知识

