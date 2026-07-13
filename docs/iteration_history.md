# InsightPilot 版本迭代记录

本文件用于对应原始计划 `InsightPilot_AI_Product_Portfolio_Plan.md`，记录从产品定义到 Demo、校验、评测和作品集材料的迭代过程。

## 版本总览

| 版本 | 对应计划阶段 | 目标 | 结果 |
|---|---|---|---|
| V0 | 产品定义 | 明确用户、场景、范围和项目结构 | 完成项目骨架和文档骨架 |
| V1 | 第一阶段：上传与体检 | 跑通数据入口和数据质量检查 | 完成 CSV/XLSX 上传、预览、字段体检 |
| V2 | 第二阶段：分析闭环 | 跑通自然语言问题到 Python 分析结果 | 完成意图、计划、执行、图表、溯源 |
| V3 | 第三阶段：校验与评测 | 加入结果验证、Bad Case 和批量评测 | 完成校验层、6 条初始评测 |
| V4 | Bad Case 迭代 | 修复描述性统计和异常分析缺口 | 扩展到 32 条测试，全部通过 |
| V5 | 作品集整理 | 补齐 PRD、复盘、验证报告和作品集成稿 | 形成可演示作品集候选版 |
| V6 | 可控工作流增强 | 让用户可以编辑、追问并查看执行过程 | 完成字段映射、清洗规则、计划编辑、追问、事件日志和模型适配器接口 |

## V0：产品定义与项目骨架

### 为什么做

原始计划明确指出项目目标不是一个“上传 Excel 后聊天”的浅 Demo，而是要展示 AI 产品经理对用户需求、Agent 流程、工具分工、校验机制和评测体系的理解。

### 做了什么

- 确认产品名称：InsightPilot
- 确认核心用户：定期处理 Excel 报表的业务分析人员
- 确认主场景：企业费用分析
- 建立项目目录：
  - `app.py`
  - `src/models`
  - `src/services`
  - `src/tools`
  - `data`
  - `docs`
  - `tests`
  - `prompts`

### 产物

- `README.md`
- `.env.example`
- `requirements.txt`
- `docs/PRD.md`
- `docs/portfolio_outline.md`

## V1：上传与数据体检

### 为什么做

原始计划第 23 节要求第一阶段不调用大模型 API，先完成上传、预览、字段类型识别、缺失值、重复值、金额格式和日期格式检测。

### 做了什么

- 实现 CSV/XLSX 文件解析
- 实现数据预览
- 实现字段类型识别
- 实现缺失值和重复值统计
- 实现金额格式检测：
  - 货币符号
  - 千分位逗号
  - 前后空格
  - 无法转换数值
- 实现日期格式检测
- 生成带脏数据的费用样例

### 关键文件

- `src/tools/file_parser.py`
- `src/tools/data_profiler.py`
- `data/generate_sample_data.py`
- `data/sample_expenses_dirty.csv`
- `tests/test_file_parser.py`
- `tests/test_data_profiler.py`

### 验证方式

- 单元测试验证文件解析和数据体检逻辑
- Streamlit 页面验证上传和预览流程

## V2：自然语言到分析结果闭环

### 为什么做

原始计划要求第二阶段完成自然语言问题输入、问题解析、分析计划生成、用户确认计划、Python 工具调用、柱状图/折线图、结果页面和公式/代码展示。

为了保证 Demo 稳定，当前没有先接真实 LLM，而是用规则版 `llm_service` 模拟结构化输出。

### 做了什么

- 新增 Pydantic 结构化模型：
  - `AnalysisIntent`
  - `AnalysisPlan`
  - `AnalysisResult`
- 实现规则版问题解析
- 实现分析计划生成
- 实现用户确认后执行
- 实现部门同比计算
- 实现增长最快部门识别
- 实现费用类型贡献下钻
- 实现月度趋势图
- 实现公式和 Python 代码溯源

### 关键文件

- `src/models/intent.py`
- `src/models/plan.py`
- `src/models/result.py`
- `src/services/llm_service.py`
- `src/services/task_service.py`
- `src/tools/analysis_tools.py`
- `src/tools/chart_tools.py`

### 验证方式

- 单元测试验证意图解析、计划生成和部门同比分析
- Demo 页面验证“问题 → 计划 → 执行 → 结果”闭环

## V3：结果校验与初始批量评测

### 为什么做

原始计划强调本项目最重要的技术亮点是结果验证机制，不能让模型直接生成未经校验的数字和结论。

### 做了什么

- 新增字段合法性校验
- 新增数值一致性校验
- 新增排名校验
- 新增文字与数字一致性校验
- 新增图表与数据一致性校验
- 新增因果表达限制校验
- 新增批量评测服务
- 新增 Bad Case 日志导出

### 初始发现的问题

初始 6 条测试中，2 条失败：

| 用例 | 问题 | 原因 |
|---|---|---|
| TC001 | 各部门总费用是多少 | 缺普通描述性统计工具 |
| TC005 | 哪些记录属于异常大额费用 | 缺异常明细分析工具 |

### 关键文件

- `src/models/validation.py`
- `src/tools/validation_tools.py`
- `src/services/evaluation_service.py`
- `tests/test_validation_tools.py`
- `docs/evaluation_results.csv`
- `docs/bad_cases_log.csv`

## V4：基于 Bad Case 的功能迭代

### 为什么做

TC001 和 TC005 是有价值的失败点。它们说明产品不能只覆盖主场景的同比分析，还需要覆盖业务用户高频的普通汇总和异常分析。

### 做了什么

#### 修复 TC001：描述性统计

- 增加 `department_summary` 意图类型
- 增加部门费用汇总工具
- 增加部门费用占比
- 增加费用最高部门识别
- 增加部门总额柱状图
- 增加汇总结果校验

#### 修复 TC005：异常分析

- 增加 `anomaly_detection` 意图类型
- 增加 IQR 异常阈值计算
- 增加异常大额费用明细表
- 增加最大异常金额指标
- 增加异常值分布图
- 增加异常阈值一致性校验

#### 扩展测试集

- 从 6 条扩展到 32 条
- 增加标准答案表
- 覆盖描述性统计、对比、趋势、下钻、异常、错误字段六类问题

### 关键文件

- `data/test_cases.csv`
- `data/standard_answers.csv`
- `src/services/llm_service.py`
- `src/services/task_service.py`
- `src/tools/analysis_tools.py`
- `src/tools/chart_tools.py`

### 当前评测结果

| 指标 | 结果 |
|---|---:|
| 用例数 | 32 |
| 任务完成率 | 100% |
| 任务理解准确率 | 100% |
| 校验通过率 | 100% |
| 澄清率 | 18.8% |

说明：当前结果基于规则版意图解析和样例数据，不代表真实 LLM 泛化能力。

## V5：作品集材料整理

### 为什么做

原始计划要求最终交付物不仅包括 Demo，还包括测试数据、评测结果、15-20 页作品集、精简 PRD、项目复盘和结构清晰的仓库。

### 做了什么

- 更新 PRD 到当前功能范围
- 补 17 页作品集成稿
- 补项目复盘
- 补进度清单
- 补集中验证报告
- 补 Markdown 分析报告导出
- 清理缓存和系统文件

### 关键文件

- `docs/PRD.md`
- `docs/portfolio_outline.md`
- `docs/project_review.md`
- `docs/progress_checklist.md`
- `docs/verification_report.md`
- `docs/latest_analysis_report.md`

## V6：可控、可追问、可观测的分析工作流

### 为什么做

V5 已经能完成分析，但用户只能接受默认字段和默认计划，无法解释一次追问如何复用上一次口径。下一步要把“可修改、可复核”从产品原则变成真实操作。

### 做了什么

- 增加业务字段到标准字段的映射配置。
- 增加缺失金额、重复记录、异常值和文本规范化清洗规则。
- 增加计划步骤启用/停用、顺序和描述编辑。
- 增加计划依赖校验，必要步骤停用时阻止执行。
- 增加“排除异常值后重新分析”等上下文追问。
- 增加任务、意图、计划、工具、校验和失败事件日志。
- 增加规则版解析器与 OpenAI 解析器的统一适配边界。
- 增加 5 个 V6 工作流测试，测试总数从 11 个增加到 16 个。

### 验证结果

- `pytest`：16 passed。
- `python -m compileall -q app.py src tests`：通过。
- Streamlit AppTest：6 个 Tab、V6 控件渲染正常、页面异常 0。
- 详细记录：`docs/v6_verification_report.md`。

## 当前仍未完成

以下内容属于 V7-V9 或最终交付项，目前还没有完成：

- 真实 OpenAI API 调用与线上错误兜底
- 纯 LLM、LLM + Python、LLM + Python + 校验三方案对比
- Token、API 成本和模型响应时间统计
- 多文件关联
- 数据库连接、企业权限管理和团队协作
- 多 Agent、RAG、模型微调和自动生成 PPT
- 停止任务、失败重试和事件日志持久化
- Demo 录屏、作品集 PDF 视觉排版和 GitHub 远程仓库发布

## V7-V9：后续产品路线

当前项目先停在 V5 候选版，后续不按功能名词堆叠，而按产品风险推进：

- V7 解决数据规模和技术方案选择：多文件关联、三方案评测、Token、成本和响应时间统计。
- V8 解决企业使用边界：只读数据库连接、角色权限、审计日志和可共享分析资产。
- V9 解决分析结果交付：基于已校验结果生成固定模板 PPT。

多 Agent、RAG 和模型微调暂不直接进入核心执行链路。它们分别要等任务复杂度、指标口径知识需求和脱敏标注数据达到条件后再引入。完整优先级、数据契约和验收标准见 `docs/next_phase_roadmap.md`。

## 当前交付物索引

| 交付物 | 文件 |
|---|---|
| 可运行 Demo | `app.py` |
| 测试数据 | `data/sample_expenses_dirty.csv` |
| 测试问题 | `data/test_cases.csv` |
| 标准答案 | `data/standard_answers.csv` |
| 评测结果 | `docs/evaluation_results.csv` |
| Bad Case 记录 | `docs/bad_cases.md` |
| 验证报告 | `docs/verification_report.md` |
| PRD | `docs/PRD.md` |
| 作品集成稿 | `docs/portfolio_outline.md` |
| 项目复盘 | `docs/project_review.md` |
| 进度清单 | `docs/progress_checklist.md` |
| 分析报告样例 | `docs/latest_analysis_report.md` |
