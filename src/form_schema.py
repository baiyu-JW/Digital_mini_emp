"""任务表单 Schema 与校验（准入校验层）。

赛题要求：准入阶段发现材料缺失时任务应暂停并提示发起人补充。
本模块返回【所有】缺失/非法项（而非第一个），便于界面一次性提示补齐。
"""

TASK_FORM_SCHEMA = {
    "period": {
        "type": "text", "required": True, "description": "统计周期",
    },
    "sales_file": {
        "type": "file", "required": True, "description": "销售明细文件",
        "accept": ["xlsx", "csv"],
    },
    "meeting_file": {
        "type": "file", "required": True, "description": "周会纪要文件",
        "accept": ["docx", "txt"],
    },
}


def check_form(form_data):
    """校验表单。

    返回 (is_valid: bool, missing: list[str])。
    missing 列出所有缺失或非法字段的可读描述，供界面提示"补充哪些材料"。
    """
    missing = []
    for name, rules in TASK_FORM_SCHEMA.items():
        if not rules.get("required"):
            continue
        val = form_data.get(name)
        if not val:
            missing.append(rules["description"])
            continue
        # 文件类型校验（界面已限制 type，此处再兜底，防止其他入口绕过）
        if rules["type"] == "file" and rules.get("accept"):
            ext = str(val).rsplit("。", 1)[-1].lower() if "." in str(val) else ""
            if ext not in rules["accept"]:
                missing.append(f"{rules['description']}(格式应为{rules['accept']})")
    if missing:
        return False, missing
    return True, []
