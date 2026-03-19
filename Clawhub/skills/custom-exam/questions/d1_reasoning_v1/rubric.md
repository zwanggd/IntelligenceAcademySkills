---
question_id: d1_reasoning_v1
dimension: reasoning
version: v1
---

# Hard Checks

## HC1
- name: 明确推荐一个方案
- max_score: 2
- pass_condition: 明确选择 A / B / C 其中一个，并给出清晰结论
- fail_condition: 没有明确推荐，或模糊表述成“都可以/看情况”

## HC2
- name: 解释不推荐另外两个方案
- max_score: 2
- pass_condition: 对另外两个未选方案分别给出至少一个不推荐理由
- fail_condition: 只推荐了一个方案，但没有分析另外两个方案为何不选

## HC3
- name: 包含落地顺序建议
- max_score: 1
- pass_condition: 给出未来 8 周的阶段性推进顺序，至少分为 2 个阶段
- fail_condition: 没有落地顺序，或只有一句空泛建议

## HC4
- name: 包含风险与缓解
- max_score: 1
- pass_condition: 至少写出 2 个具体风险，并给出对应缓解措施
- fail_condition: 没有风险部分，或只有泛泛而谈的风险提醒

# Soft Checks

## SC1
- name: 约束对齐度
- max_score: 4
- scoring_guide:
  - 0: 几乎没有使用团队约束，像通用模板答案
  - 1: 提到少量约束，但没有真正影响判断
  - 2: 使用了部分关键约束，但取舍不充分
  - 3: 结合了大部分关键约束，结论较合理
  - 4: 充分结合 2 周见效、权限敏感、2 人团队、预算中等、未来接入内部知识库等约束，形成清晰取舍

## SC2
- name: 推理完整性
- max_score: 4
- scoring_guide:
  - 0: 只有结论，没有论证
  - 1: 论证非常薄弱，停留在表面优缺点
  - 2: 有基本论证，但缺乏权衡逻辑
  - 3: 展示了较清晰的取舍和因果链条
  - 4: 论证完整，能解释为什么短期目标与长期需求之间需要这样平衡

## SC3
- name: 落地建议可执行性
- max_score: 3
- scoring_guide:
  - 0: 无法执行，只有空泛建议
  - 1: 有阶段划分，但非常模糊
  - 2: 基本可执行，阶段安排较合理
  - 3: 明确、现实，能看出对 8 周推进节奏有实际把握

## SC4
- name: 风险意识与缓解质量
- max_score: 2
- scoring_guide:
  - 0: 风险泛泛而谈，没有缓解措施
  - 1: 提到风险，但缓解措施不具体
  - 2: 风险具体，缓解措施对路且与所选方案匹配

## SC5
- name: 表达清晰度与结构
- max_score: 1
- scoring_guide:
  - 0: 结构混乱，不符合要求
  - 1: 结构清楚，表达顺畅，易于决策者快速阅读

# Score Cap Rule

- enabled: true
- if_hard_below: 3
- total_score_cap: 10

# Failure Tags

Possible tags:
- missed_constraint
- weak_reasoning
- poor_structure
- incomplete_output
- weak_risk_analysis
- low_actionability
- no_clear_recommendation
- shallow_tradeoff_analysis

# Judge Notes

高分答案通常会推荐方案 C，或者在非常强的论证下推荐 A，但关键不在“选哪个”，而在于是否真正处理了以下张力：
- 管理层要求 2 周内看到结果
- 数据权限敏感
- 团队只有 2 人
- 未来 3 个月内要接内部知识库

中分答案常见问题：
- 只说哪个方案“平衡”却没有解释平衡在哪里
- 完全忽略未来内部知识库需求
- 没有把 2 周见效作为强约束
- 风险部分只有空话

明显低分触发条件：
- 没有明确推荐
- 不分析未选方案
- 完全不写落地顺序
- 不写风险缓解
