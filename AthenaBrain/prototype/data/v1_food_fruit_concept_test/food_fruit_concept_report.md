# Food-Fruit Concept Formation Test

## Purpose
Validate whether Athena can form a small knowledge tree from events, not from a prebuilt taxonomy.

## Lessons
- Apple is a Fruit.
- Apple can be eaten.
- Grape is a Fruit.
- Grape can be eaten.
- Cookie is a Food.
- Food is something edible.

## Curiosity Before External Answer
- Food / more_examples_needed: 除了这些例子，什么样的东西也可以属于 Food？
- Fruit / more_examples_needed: 除了这些例子，什么样的东西也可以属于 Fruit？
- Food / classify_against_known_category: Food 是不是一种 Fruit，还是和 Fruit 不同？
- Fruit / classify_against_known_category: Fruit 是不是一种 Food，还是和 Food 不同？
- Apple / attribute_scope_unclear: Apple 的 edibility 是普遍特征、常见特征，还是只适用于部分例子？
- Grape / attribute_scope_unclear: Grape 的 edibility 是普遍特征、常见特征，还是只适用于部分例子？
- Apple / mentioned_concept_needs_identity: Apple 是什么？它和当前学习主题有什么关系？
- Cookie / mentioned_concept_needs_identity: Cookie 是什么？它和当前学习主题有什么关系？
- Food / attribute_scope_unclear: Food 的 edibility 是普遍特征、常见特征，还是只适用于部分例子？
- Fruit / parent_concept_needs_common_attributes: Fruit 的共同特征是什么？这些例子为什么都属于 Fruit？
- Food / mentioned_concept_needs_identity: Food 是什么？它和当前学习主题有什么关系？
- Fruit / mentioned_concept_needs_identity: Fruit 是什么？它和当前学习主题有什么关系？

## Curiosity Groups
- hierarchy: 2
- examples: 2
- identity: 4
- attribute_scope: 3
- relation_meaning: 0
- other: 1

## External Answer
Fruit is a Food.

## Validation Observations
- Event records persisted: 7
- Fruit examples after learning: ['Apple', 'Grape']
- Food examples after learning: ['Cookie', 'Fruit']
- Fruit relations after external answer: [('is-a', 'Food')]
- Athena asked a Food/Fruit relation question before the external answer.
- Curiosity groups before answer: hierarchy=2, examples=2, identity=4, attribute_scope=3, relation_meaning=0, other=1

## Remaining Issues
