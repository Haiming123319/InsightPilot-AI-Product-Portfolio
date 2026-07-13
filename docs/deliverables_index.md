# InsightPilot 交付物索引

本项目按原始计划整理为以下交付物。

## 1. 可运行 Demo

| 文件 | 说明 |
|---|---|
| `app.py` | Streamlit 主入口 |
| `src/` | 产品逻辑、工具、服务和模型 |
| `requirements.txt` | 运行依赖 |
| `.env.example` | 环境变量示例 |

运行方式：

```bash
streamlit run app.py
```

## 2. 测试数据与评测结果

| 文件 | 说明 |
|---|---|
| `data/sample_expenses_dirty.csv` | 示例费用脏数据 |
| `data/generate_sample_data.py` | 示例数据生成脚本 |
| `data/test_cases.csv` | 32 条测试问题 |
| `data/standard_answers.csv` | 标准答案表 |
| `docs/evaluation_results.csv` | 批量评测结果 |
| `docs/bad_cases_log.csv` | 当前 Bad Case 日志 |
| `docs/verification_report.md` | 集中验证报告 |
| `docs/v6_verification_report.md` | V6 工作流验证报告 |

## 3. 作品集文档

| 文件 | 说明 |
|---|---|
| `docs/portfolio_outline.md` | 17 页作品集成稿 |
| `docs/PRD.md` | 精简 PRD |
| `docs/project_review.md` | 项目复盘 |
| `docs/iteration_history.md` | 版本迭代记录 |
| `docs/progress_checklist.md` | 完成/未完成清单 |
| `docs/evaluation_plan.md` | 评测计划与当前结果 |
| `docs/bad_cases.md` | 历史 Bad Case 与修复记录 |
| `docs/latest_analysis_report.md` | 分析报告导出样例 |

## 4. 后续规划

| 文件 | 说明 |
|---|---|
| `docs/next_phase_roadmap.md` | V6-V9 路线、功能优先级、架构边界和验收门槛 |

## 5. Prompt 草稿

| 文件 | 说明 |
|---|---|
| `prompts/parse_intent.txt` | 用户问题解析 Prompt |
| `prompts/generate_plan.txt` | 分析计划生成 Prompt |
| `prompts/explain_result.txt` | 结果解释 Prompt |

## 6. 测试代码

| 文件 | 说明 |
|---|---|
| `tests/test_file_parser.py` | 文件解析测试 |
| `tests/test_data_profiler.py` | 数据体检测试 |
| `tests/test_analysis_tools.py` | 分析执行测试 |
| `tests/test_validation_tools.py` | 校验与批量评测测试 |
| `tests/test_v6_workflow.py` | V6 配置、追问、计划、日志和模型适配器测试 |

## 7. 当前未交付

- Demo 录屏
- PDF 视觉版作品集
- 真实 OpenAI API 调用与线上错误兜底
- 更完整的多轮追问
- 三方案对比实验
- Token、API 成本和模型响应时间统计
- 多文件关联
- 数据库连接、企业权限管理和团队协作
- 多 Agent、RAG、模型微调和自动生成 PPT
- GitHub 远程仓库链接

已完成但仍为可选能力的 V6 适配器：`requirements-llm.txt` 只用于安装真实模型 SDK，默认 Demo 不调用外部 API。

这些能力已经有明确的版本规划，但不应被表述为当前已实现功能。请查看 `docs/next_phase_roadmap.md`。
