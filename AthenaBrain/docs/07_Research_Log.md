## Research Log（研究日志：持续记录与可复现）

> 任何新想法、实验结果、架构修改，都必须在此记录：**验证了什么 / 推翻了什么 / 下一步是什么**。

---

## 索引（滚动追加）
- 2026-06-29：建立 AthenaBrain 文档体系；定义 Phase 1 Apple Test
- 2026-06-29：新增 State Manager 规格与 Phase 1 Apple Test 实验协议
- 2026-06-29：补齐 Phase 1 Apple Test 手工样例输出基线
- 2026-06-29：建立 BabyBrain 最小模块化原型
- 2026-06-29：验证 BabyBrain 跨运行增量概念更新
- 2026-06-29：加入候选抽象属性生成
- 2026-06-29：加入最小 Attribute Normalization 层
- 2026-06-29：加入最小 Abstraction Maturation 策略
- 2026-06-29：加入最小 Evidence Independence 验证
- 2026-06-29：确定 Belief Revision 方向：临时相信 + 证据修正
- 2026-06-29：实现 Evidence Ledger 与两个 Belief Revision 测试
- 2026-06-29：验证多概念到父概念的早期抽象（Fruit）
- 2026-06-29：验证水果课程学习：正例、边界例、反例修正 Fruit 概念

---

## 记录模板

### [日期] 实验/讨论标题
- **目标**：
- **背景**：引用 `docs/` 内相关章节
- **假设**：
- **方法**：数据/流程/prompt/代码路径
- **结果**：
- **证据**：文件/截图/输出引用
- **结论**：
- **决策**：
- **后续文档改动**：

---

## 2026-06-29 初始化
- **定位统一**：我们是 **AGI 架构研究者**，研究“持续成长的智能架构”，而非“怎么调用 GPT”。
- **文档建立**：完成 `00_Vision.md` 与编号文档骨架（01~07）。
- **Phase 1 验收**：把“苹果概念形成”固化为可执行标准（见 `02_Cognitive_Spec.md`）。
- **设计决策补全（来自 `Athena Brain Design.docx`）**：
  - Phase-1 **不自研视觉模型**：使用开源视觉模型作为 Vision Interface，只产出 Observation/Perception，不直接注入概念结论。
  - “不要背 Wikipedia”的操作化：**Athena 学证据，不学答案**；引入证据优先级与置信度渐进增长。
  - 认知管线升级：在架构里加入 **Perception**，并把 **Theory** 作为长期目标占位（见 `00_Vision.md`、`03_Architecture.md`、`05_Sleep_Engine.md`、`06_Concept_Graph.md`）。
- **新增核心假设（来自 `Athena Brain.docx` + 今日补充）**：
  - **State-based Intelligence**：智能来自“认知状态层级 + 状态迁移规则”的持续演化，而非静态参数知识。
  - **External vs Internal State**：External State 描述世界；Internal State（Attention/Curiosity/Conflict/Mental Model/Identity 等）将成为主要驱动力。
  - **长期验证点**：Internal State 是否能驱动“非输入直接触发”的主动提问与自我修正（例如由冲突与未解问题演化出的追问）。
- **下一步落地文档**：
  - 新增 `08_State_Manager.md`：定义 External State、Internal State、StateTransitionEvent、状态迁移规则、苹果/鲸鱼例子与 Phase 1 验收标准。
  - 新增 `experiments/phase1_apple_test/README.md`：把 Apple Test 改写成可执行实验协议，明确输入、步骤、输出文件、通过标准与失败标准。
- **实验基线**：
  - 在 `experiments/phase1_apple_test/outputs/` 下补齐 `01~09` 手工样例输出。
  - 这些文件用于约束第一版 BabyBrain 原型：代码应先稳定生成相同结构的证据链，再考虑更复杂的视觉/记忆/自治能力。
- **原型结构纠偏**：
  - 明确 `run_apple_test.py` 不应是“机械生成 JSON”的脚本，而只是一次实验入口。
  - 新增 `prototype/athena_brain/` 模块化原型：`StateManager`、`PerceptionInterface`、`JsonMemoryStore`、`ConceptGraph`、`SleepEngine`、`CognitiveEngine`。
  - 第一版原型已经能从用户陈述、感知特征与反馈中生成状态、Perception、Experience、Sleep Report 和早期 Concept。
  - 当前限制：概念已能跨运行加载并更新，但 Experience 检索、真实视觉模型和成熟抽象生成仍未完成。
- **增量学习验证**：
  - `CognitiveEngine` 启动时会从 `prototype/data/` 加载已有 Concept。
  - `run_incremental_apple_learning.py` 验证了第二次观察绿色苹果时，会更新同一个 Apple Concept，而不是新建机械定义。
  - `ConceptGraph` 已加入关系去重、问题去重和重复属性证据合并。
  - `SleepEngine` 已能检测同一属性的不同表现（例如 red/green color），并生成“该属性是否允许多种表现”的开放问题。
- **当前疑难点**：
  - “属性差异”已经可以升级为候选抽象（例如 `Apple color can vary: red/green`），但还不是成熟概念属性。
  - “冲突”和“变体”还需要区分：红色/绿色苹果不是矛盾，而是概念范围扩展；但某些冲突可能真的是错误证据。
  - `smooth` 与 `smooth and reflective` 这类描述粒度差异，已通过最小 `AttributeNormalizer` 暂时归为兼容描述，不再生成 `surface_variation`。
  - 当前归一化是规则式的，只能覆盖少数颜色/形状/表面词；未来需要更强的语义归一化。
  - 下一步应研究：什么时候把多条观察从 `generalized_candidate` 提升为更成熟的 `generalized_attribute`。
- **候选抽象生成**:
  - `SleepEngine` 现在会扫描同一 Concept 下同名属性的多个不同观察值。
  - 当一个属性出现多个不同证据值时，会生成概念级候选抽象，例如 `color can vary: red / green`。
  - `CognitiveEngine.describe_concept()` 会优先展示候选抽象，再展示底层观察证据。
- **属性归一化**：
  - 新增 `AttributeNormalizer`，用于把属性观察转为规范值。
  - `color`/`shape` 默认作为 variation 处理；`surface` 先作为 compatible traits 处理。
  - 运行增量学习后，Apple 只保留 `color_variation` 候选抽象；surface 被描述为“兼容补充描述”。
- **抽象成熟机制**：
  - 新增 `AbstractionPolicy`，根据不同取值数量、证据数量和基础置信度决定抽象状态。
  - `generalized_candidate` 可在证据足够时提升为 `generalized_attribute`。
  - 当前运行中，`Apple color can vary: green / red` 已可被提升为较稳定的概念级抽象。
- **新增疑难点**：
  - 当前“证据数量”已经开始引入 `sample_id`，但还没有完整 source diversity / user diversity / time diversity。
  - 重复运行同一脚本不应增加独立样本数；不同图片/不同样本才应更强地推动抽象成熟。
  - 下一步应继续为 Experience 增加更细粒度的 source diversity / sample identity / independence score 使用策略。
- **证据独立性**：
  - `Perception` 与 `Experience` 增加 `sample_id`。
  - `Experience` 增加 `source_identity`、`source_diversity`、`independence_score`。
  - `AbstractionPolicy` 现在同时考虑 `distinct_value_count`、`evidence_count` 与 `independent_sample_count`。
  - `run_clean_independence_test.py` 验证：红苹果样本 + 绿苹果样本可以让 `color can vary: green / red` 变为较稳定抽象。
  - `run_duplicate_sample_test.py` 验证：重复同一红苹果样本不会产生颜色变体抽象。
- **Belief Revision 决策**：
  - 暂不建立复杂 trust weighting。
  - 采用“临时相信 + 后续修正”：用户、图片、百科、模型输出都进入 Evidence Ledger。
  - Evidence 通过 `provisional` / `confirmed` / `disputed` / `invalidated` / `contaminated` 表达状态。
  - 图片感知默认是直接证据，但如果用户指出图片有问题，应撤销/污染其下游证据。
  - Wikipedia/reference 作为对照证据，不自动覆盖直接经历。
- **Evidence Ledger 实现**：
  - 新增 `Claim`、`Evidence`、`ValidationEvent` 数据结构。
  - 新增 `EvidenceLedger`，统一保存证据状态与验证事件。
  - `ConceptGraph` 现在会读取 Evidence 状态：`invalidated` / `disputed` 证据不能继续支撑属性或关系。
  - `run_image_invalidation_test.py` 验证图片样本被撤销后，下游属性/关系失去支撑。
  - `run_reference_conflict_test.py` 验证 reference 冲突时不直接覆盖，而是标记 disputed 并生成问题。
  - 当前仍未实现长期 `SourceProfile`；来源可靠性先通过 Evidence 历史间接体现。
- **多概念抽象验证**：
  - 新增 `run_fruit_generalization_test.py`。
  - BabyBrain 依次学习 `Apple is-a Fruit`、`Peach is-a Fruit`、`Pear is-a Fruit`。
  - `ConceptGraph.generalize_parent_concepts()` 会根据多个 `is-a` 关系创建/更新父概念。
  - `Fruit.examples` 现在可记录 `Apple`、`Peach`、`Pear`。
  - `Fruit` 可生成候选共同属性，例如多个水果例子共享 `use: can be eaten`。
  - 当前限制：共同属性聚合还很朴素，容易把“常见特征”误当作“必要特征”；需要后续反例和边界样本来修正。
- **水果课程学习**：
  - 新增 `run_fruit_curriculum_test.py`。
  - 课程包含 `Apple`、`Peach`、`Pear`、`Banana`、`Tomato` 正例，以及 `PlasticApple` 反例。
  - `Fruit` 现在可记录正例 examples 与 counterexamples。
  - 后续样本会修正早期过度概括：例如 Apple/Peach 可能让 Athena 暂时认为水果常见为圆形，但 Banana 加入后该共同属性不再被保留。
  - 当前 Fruit 候选共同属性更接近：`can be eaten`、`grows from a plant`。
  - 下一步疑难点：区分“必要条件”“常见特征”“边界条件”，例如番茄、不可食用果实、塑料水果模型。

