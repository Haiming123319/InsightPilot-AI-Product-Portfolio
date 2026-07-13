from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path


OUTPUT = Path(__file__).with_name("sample_expenses_dirty.csv")
RANDOM_SEED = 42


def main() -> None:
    random.seed(RANDOM_SEED)
    departments = ["市场部", "销售部", "研发部", "财务部", "人力资源部", "运营部"]
    expense_types = ["差旅费", "广告投放", "办公用品", "软件订阅", "培训费", "会议费", "咨询费"]
    regions = ["上海", "北京", "深圳", "杭州", "成都", "广州"]
    projects = ["新产品推广", "客户增长", "内部系统升级", "品牌活动", "渠道拓展"]
    statuses = ["已通过", "待审批", "已拒绝"]

    rows: list[dict[str, str]] = []
    start = date(2024, 1, 1)
    for index in range(720):
        current_date = start + timedelta(days=random.randint(0, 730))
        department = random.choice(departments)
        expense_type = random.choice(expense_types)
        amount = round(random.uniform(120, 28000), 2)

        if current_date.year == 2025 and department == "市场部" and expense_type in {"差旅费", "广告投放"}:
            amount *= 2.25
        elif current_date.year == 2025 and department == "市场部":
            amount *= 1.25
        elif current_date.year == 2025 and department != "市场部":
            amount *= 0.96

        row = {
            "date": current_date.isoformat(),
            "department": department,
            "expense_type": expense_type,
            "amount": f"{amount:.2f}",
            "employee": f"员工{random.randint(1, 80):03d}",
            "project": random.choice(projects),
            "region": random.choice(regions),
            "approval_status": random.choices(statuses, weights=[0.76, 0.18, 0.06])[0],
            "empty_notes": "",
        }
        rows.append(row)

    dirty_indexes = random.sample(range(len(rows)), 60)
    for offset, row_index in enumerate(dirty_indexes):
        row = rows[row_index]
        if offset % 6 == 0:
            row["amount"] = f"¥{float(row['amount']):,.2f}"
        elif offset % 6 == 1:
            row["amount"] = f" {row['amount']} "
        elif offset % 6 == 2:
            row["amount"] = ""
        elif offset % 6 == 3:
            row["department"] = row["department"] + " "
        elif offset % 6 == 4:
            row["expense_type"] = "广告费" if row["expense_type"] == "广告投放" else row["expense_type"]
        else:
            row["date"] = row["date"].replace("-", "/")

    rows[15]["amount"] = "980000.00"
    rows[31]["date"] = "2023-12-28"
    rows[49]["date"] = "not-a-date"
    for index in range(18):
        rows.append(
            {
                "date": f"2025-{(index % 6) + 1:02d}-15",
                "department": "市场部",
                "expense_type": "广告投放" if index % 2 == 0 else "差旅费",
                "amount": f"{52000 + index * 1800:.2f}",
                "employee": f"员工{90 + index:03d}",
                "project": "新产品推广",
                "region": "上海",
                "approval_status": "已通过",
                "empty_notes": "",
            }
        )
    rows.extend([rows[8].copy(), rows[27].copy(), rows[128].copy()])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
