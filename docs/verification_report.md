# InsightPilot 验证报告

更新时间：2026-07-13

## 1. 验证结论

当前项目已完成一次完整本地验证：

- 单元测试：16 passed
- Python 编译检查：通过
- 批量评测：32 条用例，32 条通过
- 标准答案表：32 条
- Bad Case 日志：当前为空，表示本轮测试集内没有失败用例
- V6 页面与工作流验证：通过，详见 `docs/v6_verification_report.md`

注意：当前验证基于规则版意图解析和样例数据，不代表真实 LLM 接入后的泛化表现。

## 2. 验证文件位置

| 文件 | 内容 |
|---|---|
| `docs/verification_report.md` | 当前这份集中验证报告 |
| `docs/evaluation_results.csv` | 32 条批量评测逐条结果 |
| `docs/bad_cases_log.csv` | Bad Case 日志 |
| `data/test_cases.csv` | 32 条测试问题 |
| `data/standard_answers.csv` | 标准答案表 |
| `docs/latest_analysis_report.md` | 最近一次分析报告导出 |
| `tests/` | 单元测试 |

## 3. 单元测试记录

执行命令：

```bash
pytest
```

结果：

```text
collected 16 items
tests/test_analysis_tools.py ...        [ 27%]
tests/test_data_profiler.py ..          [ 45%]
tests/test_file_parser.py ..            [ 63%]
tests/test_validation_tools.py ....     [100%]
16 passed
```

覆盖模块：

- 文件解析
- 数据体检
- 意图解析和计划生成
- 部门同比分析
- 结果校验
- 批量评测
- Bad Case 日志结构

## 4. 编译检查记录

执行命令：

```bash
python -m compileall app.py src
```

结果：通过。

检查范围：

- `app.py`
- `src/models`
- `src/services`
- `src/tools`

## 5. 批量评测记录

数据集：

- `data/sample_expenses_dirty.csv`

测试集：

- `data/test_cases.csv`

标准答案：

- `data/standard_answers.csv`

评测结果：

| 指标 | 结果 |
|---|---:|
| 用例数 | 32 |
| 任务完成率 | 100% |
| 任务理解准确率 | 100% |
| 校验通过率 | 100% |
| 澄清率 | 18.8% |
| 平均耗时 | 5.38 ms |

用例分类：

| 类型 | 数量 |
|---|---:|
| 描述性统计 | 6 |
| 对比分析 | 6 |
| 趋势分析 | 4 |
| 下钻分析 | 4 |
| 异常分析 | 6 |
| 错误字段 | 6 |

## 6. 当前验证通过的能力

| 能力 | 状态 |
|---|---:|
| CSV/XLSX 上传 | 通过 |
| 数据预览 | 通过 |
| 字段类型识别 | 通过 |
| 缺失值统计 | 通过 |
| 重复值统计 | 通过 |
| 金额格式检测 | 通过 |
| 日期格式检测 | 通过 |
| 描述性统计 | 通过 |
| 部门同比分析 | 通过 |
| 费用类型下钻 | 通过 |
| 月度趋势分析 | 通过 |
| 异常大额费用识别 | 通过 |
| 不存在字段澄清 | 通过 |
| 数值一致性校验 | 通过 |
| 排名校验 | 通过 |
| 文字与数字一致性校验 | 通过 |
| 图表与数据一致性校验 | 通过 |
| 报告导出 | 通过 |
| 字段映射配置 | 通过 |
| 清洗规则配置 | 通过 |
| 分析计划依赖校验 | 通过 |
| 异常值追问重算 | 通过 |
| 执行事件日志 | 通过 |

## 7. 当前限制

- 评测基于规则版意图解析，不是实际 LLM。
- 尚未做纯 LLM、LLM + Python、LLM + Python + 校验三方案对比。
- 尚未统计真实 Token、API 成本和模型响应时间。
- 用户已经可以编辑字段映射、清洗规则和分析计划步骤；当前尚未持久化配置和事件日志。
- 已支持“排除异常值后重新分析”这一 V6 追问，尚未扩展更多追问类型。
- 尚未录制 Demo 视频。

## 8. 如何复现

```bash
pytest
python -m compileall app.py src
streamlit run app.py
```

打开 Demo 后，在“批量评测”页点击“运行批量评测并导出结果”，会刷新：

- `docs/evaluation_results.csv`
- `docs/bad_cases_log.csv`
