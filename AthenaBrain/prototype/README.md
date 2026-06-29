## BabyBrain Prototype

### 这不是“生成 JSON 的脚本”
`prototype/` 的目标不是机械输出一组固定文件，而是搭建 Athena Brain 的最小认知结构：

- `StateManager`：维护 External/Internal State，并让问题来自内部状态
- `PerceptionInterface`：隔离视觉/感知输入，不让视觉标签直接变成知识
- `JsonMemoryStore`：把状态、感知、经历、概念和报告持久化
- `ConceptGraph`：维护可演化的概念与关系
- `SleepEngine`：把 Experience 巩固成候选属性、关系和问题
- `AttributeNormalizer`：把观察属性归一化，区分变体、兼容描述和噪声
- `EvidenceLedger`：保存 Evidence、Claim 与 ValidationEvent，支持证据确认、争议与撤销
- `CognitiveEngine`：协调一次完整学习循环

`run_apple_test.py` 只是一次实验入口：它把“苹果是一种水果”和一组图像特征喂给认知系统，随后由系统产生状态变化、Experience、Concept 和下一步问题。

### 运行方式
在 `AthenaBrain/prototype` 目录运行：

```bash
python run_apple_test.py
```

输出会保存到：

```text
data/phase1_apple_test/
  states/
  perceptions/
  experiences/
  concepts/
  reports/
```

### 增量学习验证
在已经运行过 `run_apple_test.py` 后，可以继续运行：

```bash
python run_incremental_apple_learning.py
```

它会复用 `data/phase1_apple_test/` 中已有的 Apple Concept，再添加一个“绿色苹果”的新经历。预期结果不是覆盖旧知识，而是：

- 保留红色苹果观察
- 添加绿色苹果观察
- 去重 `Apple is-a Fruit` 关系
- 生成“Apple 的 color 是否允许多种表现？”这类 Internal State 驱动的问题
- 在证据足够时形成候选抽象，例如 `color can vary: red / green`
- 不再把 `smooth` 与 `smooth and reflective` 误判为同级变体，而是视为兼容补充描述
- 当不同取值和证据数量达到阈值时，把候选抽象提升为较稳定的 `generalized_attribute`

这一步验证的是“概念成长”，不是“再生成一个定义”。

### 证据独立性验证
可以运行两个对照测试：

```bash
python run_clean_independence_test.py
python run_duplicate_sample_test.py
```

预期结果：

- `run_clean_independence_test.py` 使用红苹果和绿苹果两个不同 `sample_id`，可以把 `color can vary: green / red` 提升为较稳定概念级抽象。
- `run_duplicate_sample_test.py` 重复同一个 `sample_id`，不会产生颜色变体抽象。

这一步防止 Athena 把“同一证据重复出现”误当成“多次独立观察”。

### Belief Revision 验证
可以运行：

```bash
python run_image_invalidation_test.py
python run_reference_conflict_test.py
```

预期结果：

- `run_image_invalidation_test.py`：用户指出图片样本有问题后，该图片相关 Evidence 被标记为 `invalidated`，由它支撑的属性/关系不再支撑概念。
- `run_reference_conflict_test.py`：reference 与用户说法冲突时，Athena 不直接覆盖，而是将原证据标记为 `disputed`，并生成需要验证的问题。

这一步验证的是“临时相信 + 后续修正”，不是固定来源评分。

### 多概念抽象验证
可以运行：

```bash
python run_fruit_generalization_test.py
python run_fruit_curriculum_test.py
```

它会让 BabyBrain 依次学习：

- `Apple is-a Fruit`
- `Peach is-a Fruit`
- `Pear is-a Fruit`

预期结果：

- `Fruit` 作为父概念被创建/更新
- `Fruit.examples` 包含 `Apple`、`Peach`、`Pear`
- `Fruit` 形成候选共同属性，例如多个水果例子都 `can be eaten`
- Athena 能说明：它当前对 `Fruit` 的理解来自这些具体例子，而不是百科定义

这一步验证的是“多个具体概念 → 上位抽象概念”。

`run_fruit_curriculum_test.py` 更进一步，加入：

- Apple / Peach / Pear / Banana / Tomato 作为 `Fruit` 正例
- PlasticApple 作为 `Fruit` 反例
- 不同形状、颜色、表面、用途、来源信息

预期结果：

- Fruit 能记录多个正例和反例
- Fruit 能保留较稳定的共同属性，例如 `can be eaten`、`grows from a plant`
- Fruit 会撤销早期过度概括，例如“水果都是圆形”
- Athena 能说明它对 Fruit 的理解来自具体样本，而不是百科定义

### Web Console
可以启动一个本地网页界面观察 Athena 的成长状态：

```bash
python web_console.py
```

然后打开：

```text
http://127.0.0.1:8765
```

第一版 Web Console 是零依赖原型，主要用于观察和验证：

- 选择不同实验数据集，例如 `phase1_apple_test`、`phase1_fruit_curriculum_test`
- 查看 Athena 当前形成的 Concepts、attributes、relations、examples、counterexamples 和 open questions
- 通过简单问答查看 Athena 对某个概念的描述，例如“描述一下 Apple”“Fruit 有什么特点”
- 查看 Athena 主动提出的好奇问题，并直接回答这些问题
- 如果同一个好奇问题收到互相冲突的回答，Athena 会把旧回答标记为 disputed，并记录新的困惑问题
- 回答来自 `ConceptGraph` 中已经学习到的经历和概念结构，不来自百科定义

当前没有接入 LLM，所以它还不是开放式聊天系统。它只能通过简单规则识别有限问题：描述、特点、知道什么，再加上概念名。未来接入 LLM 时，LLM 应作为语言理解/表达接口，把用户自然语言转成 Athena 的结构化学习动作或查询；Athena 的核心认知仍由 Experience、Evidence、ConceptGraph、SleepEngine 和 Internal State 维护。

### Curiosity Engine
`CuriosityEngine` 是 Athena 当前最小的好奇心机制。它会根据以下信号生成主动问题：

- 概念还处在 `seed` / `early` 阶段
- `Concept.open_questions` 中存在未回答问题
- 属性存在变化，例如颜色、形状、是否可食用
- 父概念有正例和反例，需要解释边界
- 同一个问题收到冲突回答，产生新的困惑

当用户回答一个好奇问题时，Athena 会把回答记录成 `user_curiosity_answer` Evidence，并尝试抽取一个候选属性，例如 `edibility`、`color`、`shape` 或 `boundary_note`。如果同一问题的新回答与旧回答不同，旧 Evidence 会被标记为 `disputed`，概念中会出现一个新的困惑问题，等待继续验证。

### 当前限制
- 视觉特征暂时由 mock/manual 输入提供。
- Sleep Engine 只做最小巩固，不做复杂抽象。
- ConceptGraph 当前仍是内存结构，但启动时会从 JSON 加载已有概念。
- 已支持最小跨运行概念更新，但还没有完整 Experience 索引和检索系统。
- 属性差异已经可以形成候选抽象，但还没有成熟到理论/规则层。
- 已加入最小抽象成熟策略，但还没有判断证据是否真正独立。
- 已加入最小证据独立性判断（基于 `sample_id`），但还没有更复杂的 source diversity / user diversity / time diversity。
- 当前只有很小的规则式属性归一化，还不是通用语义理解。
- Belief Revision 已能处理 invalidated/disputed，但还没有完整 SourceProfile 和长期来源历史。
- 父概念抽象目前只做很朴素的共同属性聚合，还没有处理“非必要属性”和“反例”。
- 课程测试已能处理简单反例，但还没有系统化区分“必要条件”“常见特征”“边界条件”。

### 下一步
下一步不是让脚本“看起来聪明”，而是补上：

- 多轮输入逐步提升 Concept 置信度
- 区分“真实冲突”“合理变体”“描述粒度差异”
- Internal State 驱动的主动问题队列
- 从候选抽象中生成更成熟的概念级属性
- 更好的属性语义归一化（未来可由 embedding/视觉模型/人工反馈共同支持）
- 更细的证据独立性判断：同一用户、同一图片、同一时间段、同一模型输出应有不同权重
- SourceProfile：记录某个来源在不同领域/不同时间的历史可靠性，但避免过早复杂化
- 反例学习：例如番茄/坚果/不可食用果实等边界样本，用于修正 Fruit 概念
- 概念层级深化：从 `Fruit` 继续走向 `PlantPart`、`Food`、`BiologicalReproduction` 等更高层理论

