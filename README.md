# InsightPilot

InsightPilot 是一个面向 AI 产品经理作品集的可验证数据分析 Copilot。当前已形成可演示作品集候选版，覆盖“上传数据 → 数据体检 → 自然语言提问 → 结构化意图 → 分析计划确认 → Python 执行 → 图表与结论 → 公式和代码溯源 → 发布前校验 → 报告导出 → 批量评测”。

## 当前阶段能力

- CSV/XLSX 单文件上传
- 示例费用数据加载
- 前 20 行数据预览
- 字段类型识别
- 缺失值统计
- 重复记录统计
- 金额格式问题检测
- 日期格式问题检测
- 数据质量问题汇总
- 自然语言分析问题输入
- 规则版结构化意图解析
- 分析计划生成与确认
- 部门费用汇总
- Python 同比计算和费用类型下钻
- 异常大额费用识别
- Plotly 图表生成
- 异常值分布图
- 核心结论、指标卡片、计算表展示
- 公式和 Python 代码溯源
- 字段合法性校验
- 数值一致性校验
- 排名校验
- 文字与数字一致性校验
- 图表与数据一致性校验
- 因果表达限制校验
- Markdown 分析报告导出
- 32 条测试集和标准答案表
- 测试集批量运行
- 评测结果和 Bad Case 日志导出

说明：当前仍不调用真实大模型 API，`src/services/llm_service.py` 先用规则模拟 LLM 结构化输出，保证 Demo 闭环可稳定运行。后续可替换为 OpenAI API 或兼容模型 API。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行 Demo

```bash
streamlit run app.py
```

## 运行测试

```bash
pytest
```

## 运行批量评测

在 Demo 的“批量评测”页点击按钮，或在 Python 中调用 `run_batch_evaluation`。当前样例测试集结果会导出到：

- `docs/evaluation_results.csv`
- `docs/bad_cases_log.csv`

当前样例评测结果：

| 指标 | 结果 |
|---|---:|
| 用例数 | 32 |
| 任务完成率 | 100% |
| 任务理解准确率 | 100% |
| 校验通过率 | 100% |
| 澄清率 | 18.8% |

## 项目结构

```text
.
├── app.py
├── data/
├── docs/
├── prompts/
├── src/
│   ├── models/
│   ├── services/
│   └── tools/
└── tests/
```

## 下一阶段建议

下一阶段建议接入真实 OpenAI API、实现可编辑字段映射和计划步骤、支持“排除异常值后重新分析”的追问、加入三方案对比实验，并录制 2-4 分钟 Demo。
