# Phase 1：真实模型意图解析报告

## 结论

在保留规则基线的前提下，InsightPilot 已将真实 OpenAI 意图解析接入 Streamlit 主流程。模型只负责把自然语言问题转换为 `AnalysisIntent`；Python 计算、工具执行和结果校验仍留在本地。当前已完成代码级和 Mock 失败路径验收，尚未宣称真实 API 的准确率、成本或线上延迟提升。

## 产品目标与非目标

目标是降低用户把业务问题翻译成固定分析任务的负担，同时不牺牲数据计算的可靠性和失败时的可恢复性。

本阶段不做分析计划驱动工具执行、不做真实模型结果解释、不做多轮追问升级、不做 RAG 或多 Agent。这些属于后续 Phase。

## 主流程

```text
用户问题 + 受限数据画像
  -> Provider Router
       -> RuleBasedIntentParser
       -> OpenAIIntentParser
       -> OpenAI 失败时按配置回退
  -> Pydantic AnalysisIntent
  -> 本地字段 / 操作 / 时间范围校验
  -> clarification_needed 或进入既有分析计划流程
```

## 交付内容与验收

| 交付 | 验收事实 |
|---|---|
| 规则基线 | `LLM_PROVIDER=rule_based` 默认可运行；原有测试不回归 |
| OpenAI 模式 | 页面可选择 `openai`；缺少 Key 或调用失败时显示可理解错误，不白屏、不自动回退 |
| OpenAI + 回退 | 页面可选择 `openai_with_fallback`；失败后回到规则解析，记录 `fallback_reason` 并写入 Bad Case 日志 |
| 结构化输出 | 优先使用 Responses API `responses.parse(..., text_format=AnalysisIntent)`；输出包含 Pydantic 校验 |
| 数据最小化 | 发送行数、日期范围、字段画像和少量脱敏样例；不发送完整 DataFrame、文件路径或 API Key |
| 本地拦截 | 不存在字段、未知操作、非法图表、时间范围不在数据区间时转换为澄清状态，执行按钮保持禁用 |
| 可观测性 | 页面展示实际 Provider、模型、耗时、输入 Token、输出 Token、总 Token 和是否回退 |
| 测试 | `pytest -q` 当前为 29 passed；新增测试全部使用注入客户端或 Mock |

## 评测设计

已覆盖：规则解析、OpenAI 结构化返回、缺少 Key、鉴权失败、超时、限流、网络错误、非法结构、字段幻觉、OpenAI 失败回退、不回退模式、Token/耗时/request_id、完整 DataFrame 不外发、文本样例脱敏。

尚未测量：真实模型任务理解准确率、真实 API 成本、真实网络 P95 延迟和规则/模型的效果差异。Phase 4 再使用固定测试集比较规则、模型、模型加回退三种方案。

## 作品集呈现方式

建议用 4 个画面和 1 个面试故事表达本阶段：

1. 架构图：模型只负责意图理解，Python 负责计算，规则负责拦截与回退。
2. 页面截图：同一问题分别选择规则、OpenAI、OpenAI + 回退，并展示 Provider/Token/耗时。
3. Bad Case 截图：模型返回不存在字段，系统转为澄清而不是执行。
4. 失败回退截图：模拟超时或无 Key，页面继续给出规则结果并保留回退原因。
5. 面试表达：我没有让大模型直接生成代码或结论，而是把不确定性隔离在意图解析层，用结构化输出、本地校验和可回退机制控制体验风险。
