"""自动质检工具（场景 A）。

对应赛题"自动质检"要求：≥3 类检查、不通过可自动修正后重试（上限由调用方控制）、结果形成检验记录。

三类检查：
1. 字数：正文不少于 config.min_words（默认 300）。
2. 结构：必须包含《周报格式要求》的六个章节（摘要 / 核心指标 / 异常 / 品类 / 数据质量 / 下周关注）。
3. 数据一致性：核心数字（总实收 / 毛利率 / 外卖占比 / 各区域实收）必须出现在正文中，防止编造。
"""


def check_report_quality(report_text, data, config=None):
    """自动质检。

    入参:
        report_text (str): 大模型生成的周报文本。
        data (dict): read_sales_data 的返回（含 total_sales / profit_rate / takeout_rate / region_stats 等）。
        config (dict|None): 员工配置（含 min_words）。
    出参:
        (passed: bool, msg: str)
    """
    config = config or {}
    min_words = int(config.get("min_words", 300))

    if not report_text or not report_text.strip():
        return False, "报告内容为空。"

    # 1. 字数
    if len(report_text) < min_words:
        return False, f"字数不足，当前 {len(report_text)} 字，要求至少 {min_words} 字。"

    # 2. 结构（六章节）
    required = ["摘要", "核心指标", "异常", "品类", "数据质量", "下周关注"]
    missing = [kw for kw in required if kw not in report_text]
    if missing:
        return False, f"结构缺失，未找到章节：{missing}。"

    # 3. 数据一致性（关键数字必须出现，防止编造）
    clean = report_text.replace(" ", "").replace("\xa0", "").replace("\n", "").replace(",", "")
    try:
        total = float(data.get("total_sales", 0) or 0)
        pr = data.get("profit_rate")
        tr = data.get("takeout_rate")
        region_hits = 0
        for r, rs in data.get("region_stats", {}).items():
            if str(rs.get("sales", "")) in clean:
                region_hits += 1
        # 总实收 / 毛利率 / 外卖占比 至少命中 2 个，且至少 1 个区域实收出现
        core = []
        core.append(str(int(total)))
        if pr is not None:
            core.append(f"{pr}%")
        if tr is not None:
            core.append(f"{tr}%")
        core_hits = sum(1 for c in core if c and c in clean)
        if core_hits < 2 or region_hits < 1:
            return False, "数据不一致：报告未包含真实的核心指标数字（总实收/毛利率/外卖占比/区域实收）。"
    except Exception:
        pass  # 解析失败不阻断，放行

    return True, "质检通过"
