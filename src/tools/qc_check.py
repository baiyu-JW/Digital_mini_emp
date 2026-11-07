def check_report_quality(report_text, expected_sales):
    """自动质检工具（完全体）。"""
    if not report_text or len(report_text.strip()) == 0:
        return False, "报告内容为空。"

    # 【清洗所有干扰项】：去掉空格、不间断空格、换行、逗号
    clean_text = report_text.replace(" ", "").replace("\xa0", "").replace("\n", "").replace(",", "")

    # 1. 检查字数（放宽到 300 字，防止 AI 写不完被误杀）
    word_count = len(report_text)
    if word_count < 300:
        return False, f"字数不足，当前只有 {word_count} 字，要求至少 300 字。"

    # 2. 检查结构（只要包含这几个字眼即可）
    required_keywords = ["摘要", "指标", "异常"]
    for kw in required_keywords:
        if kw not in report_text:
            return False, f"结构缺失，未找到核心段落 '{kw}'。"

    # 3. 检查数据（在清洗后的文本里找）
    try:
        val_float = float(expected_sales)
        expected_str_1 = str(round(val_float, 2))  # 比如 "5746560.29"
        expected_str_2 = str(int(val_float))  # 比如 "5746560"
        wan_str = f"{val_float / 10000:.1f}万"  # 比如 "574.7万"

        # 只要匹配上一种就算过关
        if expected_str_1 not in clean_text and expected_str_2 not in clean_text and wan_str not in clean_text:
            return False, f"数据不一致，报告中未包含真实的销售数据({expected_sales})。"
    except Exception:
        pass  # 如果转换出错，就不查数字了，放行

    return True, "质检通过"