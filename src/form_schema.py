TASK_FORM_SCHEMA = {
    "period": {"type": "text", "required": True, "description": "统计周期"},
    "sales_file": {"type": "file", "required": True, "description": "销售明细文件"},
    "meeting_file": {"type": "file", "required": True, "description": "周会纪要文件"}
}

# 校验函数
def check_form(form_data):
    for field_name, rules in TASK_FORM_SCHEMA.items():
        if rules["required"] and not form_data.get(field_name):
            return False, f"缺少必填项：{rules['description']}"
    return True, "表单校验通过"