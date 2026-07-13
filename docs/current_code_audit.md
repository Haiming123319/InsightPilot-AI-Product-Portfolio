# 当前代码审计

本审计记录 Phase 0 在 API 接入前对真实代码的核对结果，并标记 Phase 1 完成后的变化。

## 主流程调用关系

```text
app.main
  -> parse_file
  -> apply_field_mapping
  -> profile_dataframe
  -> render_task_creation
       -> Phase 0: parse_user_intent
       -> Phase 1: intent_parser_router.parse_intent
       -> generate_analysis_plan
       -> validate_analysis_plan
       -> execute_analysis_task
            -> execute_department_yoy_task / execute_department_summary_task / execute_anomaly_task
            -> validate_analysis_result
  -> render_result_page
       -> get_result_tables / charts / follow-up / evidence
  -> render_evaluation_page
       -> run_batch_evaluation
```

## 真实执行与规则模拟

| 模块 | 审计结论 | 证据与边界 |
|---|---|---|
| 文件解析 | 真实执行 | `src/tools/file_parser.py` 读取 CSV/XLSX，并返回 DataFrame |
| 数据画像 | 真实执行 | `src/tools/data_profiler.py` 计算缺失、重复、类型、日期范围和有限样例 |
| 规则意图解析 | 真实执行的规则基线 | `parse_user_intent` 使用关键词和字段白名单，不是模型推理 |
| OpenAI 意图解析 | Phase 1 已接入主流程 | `OpenAIIntentParser` 使用 Responses API 的 Pydantic 结构化输出；旧 Chat 适配仅保留给注入测试客户端 |
| 分析计划 | 当前仍是固定模板生成 | `generate_analysis_plan` 根据 `task_type` 生成步骤，Phase 2 才让步骤真实驱动工具 |
| 数值计算 | 真实执行 | `src/tools/analysis_tools.py` 和 `src/services/task_service.py` 使用 Pandas 计算 |
| 结果解释 | 模板生成 | `build_result`、`build_summary_result`、`build_anomaly_result` 只基于本地计算结果拼接文本 |
| 追问 | 关键词规则 | `followup_service.py` 只支持异常值和缺失金额口径切换 |
| 评测 | 规则基线评测 | `evaluation_service.py` 默认调用 `parse_user_intent`，没有伪装成真实 LLM 评测 |

## Phase 0 发现的未接入能力

在审计时，`OpenAIIntentParser` 类存在，但页面没有调用；其输入也只包含字段名，缺少数据画像和敏感数据边界。Phase 1 已通过 `intent_parser_router.py` 接入页面，并新增统一元数据与本地合法性校验。

## 计划是否真实控制执行

当前答案是：没有。计划编辑会被 `validate_analysis_plan` 校验并记录，但 `execute_analysis_task` 仍根据 `intent.task_type` 选择固定函数。该问题属于 Phase 2，当前没有提前重构，以保留基线可比性。

## 产品风险结论

Phase 0 的关键判断是：系统已经能证明“数据计算和结果校验可控”，但不能证明“真实模型能理解用户问题”。因此 Phase 1 只把模型放在意图理解边界，模型不接触完整 DataFrame、不计算数字、不生成 Python，也不直接执行工具。
