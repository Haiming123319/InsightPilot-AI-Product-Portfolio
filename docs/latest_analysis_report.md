# InsightPilot 分析报告

## 核心结论

2025 年总费用为 7,647,007，整体同比为 59.8%。市场部 是当前口径下增长最快的部门，增长主要集中在 差旅费（新增 821,118，贡献 44.4%）、广告投放（新增 662,374，贡献 35.8%）。

## 结构化结论

- 市场部 在部门同比排名中位列第 1，增长率为 248.6%。（证据：table_department_yoy）
- 2025 年总费用为 7,647,007。（证据：table_department_yoy）
- 市场部 新增费用中，差旅费 贡献最高，贡献率为 44.4%。（证据：table_expense_type_contribution）

## 限制说明

- 有 12 行因日期、金额或关键维度缺失未纳入 2024/2025 同比计算。
- 本分析是描述性分析，只能说明增长集中在哪些费用类型，不能证明因果关系。

## 各部门同比结果

| department | amount_2024 | amount_2025 | increase | yoy_growth | status | rank |
| --- | --- | --- | --- | --- | --- | --- |
| 市场部 | 740051.88 | 2579583.87 | 1839531.9900000002 | 2.4856797742342067 | 可计算同比 | 1 |
| 财务部 | 841026.15 | 1596730.47 | 755704.32 | 0.8985503245053675 | 可计算同比 | 2 |
| 人力资源部 | 777509.03 | 1263005.92 | 485496.8899999999 | 0.6244260468589026 | 可计算同比 | 3 |
| 研发部 | 857052.25 | 900188.66 | 43136.41000000003 | 0.050331132086754375 | 可计算同比 | 4 |
| 销售部 | 732358.25 | 671529.79 | -60828.45999999996 | -0.08305833927589396 | 可计算同比 | 5 |
| 运营部 | 836000.73 | 635968.76 | -200031.96999999997 | -0.23927248245345428 | 可计算同比 | 6 |

## 市场部 费用类型贡献

| expense_type | amount_2024 | amount_2025 | increase | contribution_rate |
| --- | --- | --- | --- | --- |
| 差旅费 | 166286.47 | 987403.99 | 821117.52 | 0.4437921531395407 |
| 广告投放 | 62538.79 | 724913.0 | 662374.21 | 0.3579956214306598 |
| 软件订阅 | 51588.1 | 265822.27 | 214234.17 | 0.11578786381316329 |
| 咨询费 | 143378.18 | 250765.55 | 107387.37 | 0.05804001375137204 |
| 办公用品 | 135637.46 | 173981.66 | 38344.20000000001 | 0.02072401899111004 |
| 会议费 | 91587.84 | 98360.29000000001 | 6772.450000000012 | 0.003660328874154198 |
| 培训费 | 89035.04 | 78337.11 | -10697.929999999993 | 0.0 |

## 公式与代码

### table_department_yoy

使用字段：date, department, amount

覆盖行数：726

```text
同比增长率 = (2025 年费用 - 2024 年费用) / 2024 年费用；2024 年为 0 时不输出百分比。
```

```python
cleaned = clean_expense_dataframe(df)
valid = cleaned.dropna(subset=["date_clean", "amount_clean", "department", "expense_type"])
valid = valid[valid["year"].isin([2024, 2025])]
yearly = valid.groupby(["department", "year"], as_index=False)["amount_clean"].sum()
pivot = yearly.pivot(index="department", columns="year", values="amount_clean").fillna(0)
yoy_growth = (amount_2025 - amount_2024) / amount_2024
top_department = department_yoy.sort_values(["yoy_growth", "increase"], ascending=False).iloc[0]
contribution = top_department_rows.groupby(["expense_type", "year"])["amount_clean"].sum()

```
### table_expense_type_contribution

使用字段：department, expense_type, amount

覆盖行数：726

```text
贡献率 = 某费用类型新增费用 / 增长最快部门总新增费用。
```

```python
cleaned = clean_expense_dataframe(df)
valid = cleaned.dropna(subset=["date_clean", "amount_clean", "department", "expense_type"])
valid = valid[valid["year"].isin([2024, 2025])]
yearly = valid.groupby(["department", "year"], as_index=False)["amount_clean"].sum()
pivot = yearly.pivot(index="department", columns="year", values="amount_clean").fillna(0)
yoy_growth = (amount_2025 - amount_2024) / amount_2024
top_department = department_yoy.sort_values(["yoy_growth", "increase"], ascending=False).iloc[0]
contribution = top_department_rows.groupby(["expense_type", "year"])["amount_clean"].sum()

```