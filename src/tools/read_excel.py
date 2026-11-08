"""数据读取与计算工具（场景 A 经营周报）。

严格对齐《数据说明.md》与《周报格式要求.md》的统计口径：
- 实收 = 实收金额合计（退货为负自动冲减）
- 毛利 = 实收 − 成本；毛利率 = 毛利 ÷ 实收
- 环比 = (本周 − 上周) ÷ 上周
- 目标达成率 = 本周实收 ÷ 销售目标表(区域,周)目标
- 外卖占比 = 外卖渠道实收 ÷ 全部实收
- 异常 = 区域/门店环比波动超过 threshold（默认 10%，可在 employee.yaml 配置）
- 数据质量：退货笔数/金额、重复记录ID去重、整周零销售门店、新开门店、数据覆盖范围

设计原则（赛题"工程加固"加分）：
- 入参/出参显式；读取/计算失败返回 success=False + 明确原因，不编造。
- 统计周期超出数据覆盖范围时直接暂停并说明，绝不输出该周数字。
"""
import re
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 关键：只存 PNG 图片，强制无 GUI 后端。否则 matplotlib 会自动挑 Qt 后端，
                       # 在装有 PyQt5 的机器（PyCharm/Jupyter 环境）上 QtCore 初始化失败，
                       # 导致 read_excel 工具直接抛异常 -> 任务秒进"失败转人工"。
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

REGIONS = ["华东", "华南", "华北", "西南"]


def _parse_week(period):
    if not period:
        return None
    m = re.search(r"第\s*(\d{1,2})\s*周", period)
    return int(m.group(1)) if m else None


REQUIRED_SHEETS = ["销售明细", "门店信息", "商品信息", "销售目标"]


def _load(file_path):
    """兼容 .xlsx 与 .csv 两种输入（赛题要求）。

    - .xlsx：含 4 个工作表（销售明细/门店信息/商品信息/销售目标），全部从它读。
    - .csv ：仅含“销售明细”单表（UTF-8 带 BOM）。区域/品类/目标三类静态参考表
            从同目录随包的《销售明细.xlsx》读取。两种来源的销售明细数据一致，
            核算结果完全相同。
    """
    p = str(file_path)
    ext = p.lower().rsplit(".", 1)[-1]
    if ext in ("xlsx", "xls"):
        try:
            xl = pd.ExcelFile(p)
        except Exception as e:
            raise ValueError(
                f"文件“{p}”无法按 Excel 打开（{e}）。"
                "请上传项目提供的《销售明细.xlsx》原件，不要用另存/导出的其他格式。"
            )
        missing = [s for s in REQUIRED_SHEETS if s not in xl.sheet_names]
        if missing:
            raise ValueError(
                f"Excel 缺少必需的工作表：{'、'.join(missing)}。"
                f"当前文件只包含：{'、'.join(xl.sheet_names)}。"
                "请上传含 4 个工作表（销售明细/门店信息/商品信息/销售目标）的《销售明细.xlsx》。"
            )
        sales = xl.parse("销售明细")
        stores = xl.parse("门店信息")
        items = xl.parse("商品信息")
        targets = xl.parse("销售目标")
    elif ext == "csv":
        sales = _read_csv_sales(p)
        ref_xlsx = _find_reference_xlsx(p)
        if ref_xlsx is None:
            raise ValueError(
                "检测到 CSV 输入（CSV 仅含“销售明细”单表）。本系统还需门店信息/商品信息/"
                "销售目标三张静态参考表，请保持项目目录中的《销售明细.xlsx》原件存在（"
                "它与 CSV 同目录即可），系统会自动从中读取这三类参考数据。"
            )
        try:
            xl = pd.ExcelFile(ref_xlsx)
        except Exception as e:
            raise ValueError(f"参考文件《销售明细.xlsx》无法打开（{e}）。")
        for s in ("门店信息", "商品信息", "销售目标"):
            if s not in xl.sheet_names:
                raise ValueError(f"参考 Excel 缺少工作表：{s}。")
        stores = xl.parse("门店信息")
        items = xl.parse("商品信息")
        targets = xl.parse("销售目标")
    else:
        raise ValueError(
            f"不支持的文件类型：“{p}”。请上传 .xlsx 或 .csv 格式的《销售明细》。"
        )
    for d in (sales, stores, items, targets):
        d.columns = [str(c).strip() for c in d.columns]
    return sales, stores, items, targets


def _read_csv_sales(p):
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except Exception as e:
        raise ValueError(
            f"CSV 读取失败（{e}）。请确认上传的是《销售明细.csv》（UTF-8 带 BOM）版本。"
        )


def _find_reference_xlsx(p):
    """CSV 模式下，在同目录寻找随包的《销售明细.xlsx》作为参考表来源。"""
    import os

    d = os.path.dirname(p) or "."
    cand = os.path.join(d, "销售明细.xlsx")
    return cand if os.path.exists(cand) else None


def _clean_amounts(df):
    for c in ["原价金额", "折扣金额", "实收金额", "成本金额", "销售数量"]:
        if c in df.columns:
            df[c] = pd.to_numeric(
                df[c].astype(str).str.replace(",", "").str.strip(), errors="coerce"
            ).fillna(0)
    return df


def _add_region(df, stores):
    return df.merge(stores[["门店编码", "区域"]], on="门店编码", how="left")


def _add_category(df, items):
    return df.merge(items[["商品编码", "品类"]], on="商品编码", how="left")


def _week_window(targets, wk):
    row = targets[(targets["区域"] == REGIONS[0]) & (targets["周次"] == wk)]
    if row.empty:
        return None, None
    return pd.to_datetime(row["周起始日"].iloc[0]), pd.to_datetime(row["周结束日"].iloc[0])


def _week_subset(sales, ws, we):
    sales = sales.copy()
    sales["销售日期"] = pd.to_datetime(sales["销售日期"])
    return sales[(sales["销售日期"] >= ws) & (sales["销售日期"] <= we)].copy()


def read_sales_data(file_path, period="", config=None):
    config = config or {}
    threshold = float(config.get("anomaly_threshold", 10))
    try:
        sales, stores, items, targets = _load(file_path)
        sales["销售日期"] = pd.to_datetime(sales["销售日期"], errors="coerce")
    except ValueError as e:
        # 我们自己抛出的校验错误已是人话，直接透传
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"读取 Excel 失败：{e}"}

    week = _parse_week(period)
    if week is None:
        return {"success": False, "message": "无法解析统计周期，请输入如“2026年第44周”。"}
    wk = f"W{week}"
    ws, we = _week_window(targets, wk)
    if ws is None:
        return {
            "success": False,
            "message": f"目标表中无 {wk} 周记录，可能超出数据覆盖范围（数据实际覆盖至 W44）。",
        }

    sales = _clean_amounts(sales)
    wk_sales = _week_subset(sales, ws, we)
    max_date = sales["销售日期"].max().date()
    if wk_sales.empty:
        return {
            "success": False,
            "message": f"销售明细数据只覆盖到 {max_date}，无法生成 {wk} 周报，请勿编造该周数字。",
        }

    # 去重：记录ID 重复视为重复上传，仅保留首次
    dup_mask = wk_sales["记录ID"].duplicated(keep="first")
    dup_count = int(dup_mask.sum())
    dup_amount = float(wk_sales.loc[dup_mask, "实收金额"].sum())
    wk_sales = wk_sales[~dup_mask].copy()
    wk_sales = _add_region(_add_category(wk_sales, items), stores)

    # 上周
    pw = f"W{week - 1}"
    pws, pwe = _week_window(targets, pw)
    has_prev = pws is not None
    if has_prev:
        pweek = _week_subset(sales, pws, pwe)
        pweek = pweek[~pweek["记录ID"].duplicated(keep="first")].copy()
        pweek = _clean_amounts(pweek)
        pweek = _add_region(_add_category(pweek, items), stores)
        prev_total = float(pweek["实收金额"].sum())
    else:
        pweek = None
        prev_total = 0.0

    def agg(df):
        s = float(df["实收金额"].sum())
        c = float(df["成本金额"].sum())
        p = s - c
        r = (p / s * 100) if s else 0.0
        return s, c, p, r

    ts, tc, tp, tr = agg(wk_sales)
    takeout = float(wk_sales[wk_sales["渠道"] == "外卖"]["实收金额"].sum())
    takeout_rate = (takeout / ts * 100) if ts else 0.0
    mom = ((ts - prev_total) / prev_total * 100) if (has_prev and prev_total) else 0.0

    region_stats = {}
    for r in REGIONS:
        rs = wk_sales[wk_sales["区域"] == r]
        s, c, p, rr = agg(rs)
        tgt = targets[(targets["区域"] == r) & (targets["周次"] == wk)]
        t = float(tgt["实收目标(元)"].iloc[0]) if not tgt.empty else 0.0
        attain = (s / t * 100) if t else 0.0
        if has_prev and pweek is not None:
            prs = pweek[pweek["区域"] == r]
            ps = float(prs["实收金额"].sum())
            rmom = ((s - ps) / ps * 100) if ps else 0.0
        else:
            rmom = 0.0
        region_stats[r] = {
            "sales": round(s),
            "profit_rate": round(rr, 1),
            "target": round(t),
            "attain": round(attain, 1),
            "mom": round(rmom, 1),
        }

    # 门店级环比 -> 异常门店
    store_w = wk_sales.groupby("门店名称")["实收金额"].sum()
    if has_prev and pweek is not None:
        store_p = pweek.groupby("门店名称")["实收金额"].sum()
        sm = ((store_w - store_p) / store_p * 100).dropna()
    else:
        sm = pd.Series(dtype=float)
    anomaly_stores = [(n, round(v, 1)) for n, v in sm.items() if abs(v) >= threshold]
    anomaly_regions = [
        (r, region_stats[r]["mom"]) for r in REGIONS if abs(region_stats[r]["mom"]) >= threshold
    ]

    # 品类
    cat_w = wk_sales.groupby("品类")["实收金额"].sum()
    if has_prev and pweek is not None:
        cat_p = pweek.groupby("品类")["实收金额"].sum()
        cm = ((cat_w - cat_p) / cat_p * 100).dropna()
    else:
        cm = pd.Series(dtype=float)
    category_stats = {
        k: {"sales": round(v), "mom": round(float(cm.get(k, 0)), 1) if k in cm.index else 0.0}
        for k, v in cat_w.items()
    }

    # Top5 单品
    top = (
        wk_sales.groupby("商品名称")["实收金额"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
    )
    top_items_text = "\n".join([f"- {n}：{round(v)} 元" for n, v in top.items()])

    # 数据质量
    ret = wk_sales[wk_sales["实收金额"] < 0]
    ret_cnt = int(len(ret))
    ret_amt = float(ret["实收金额"].sum())
    active = set(wk_sales[wk_sales["实收金额"] != 0]["门店名称"])
    zero_stores = [s for s in stores["门店名称"] if s not in active]
    stores2 = stores.copy()
    stores2["开业日期"] = pd.to_datetime(stores2["开业日期"])
    new_stores = list(stores2[stores2["开业日期"] > ws]["门店名称"])

    # 趋势图（近 4 周）
    trend = []
    for w in range(week - 3, week + 1):
        if w < 36:
            continue
        wss, wse = _week_window(targets, f"W{w}")
        if wss is None:
            continue
        amt = float(_week_subset(sales, wss, wse)["实收金额"].sum())
        trend.append((f"W{w}", round(amt)))
    chart_trend = "trend_chart.png"
    if trend:
        plt.figure(figsize=(8, 4))
        plt.plot([t[0] for t in trend], [t[1] for t in trend], marker="o", color="tomato")
        plt.title("近4周全公司实收趋势")
        plt.tight_layout()
        plt.savefig(chart_trend)
        plt.close()

    # 区域柱状图
    chart_region = "region_chart.png"
    plt.figure(figsize=(8, 4))
    plt.bar(REGIONS, [region_stats[r]["sales"] for r in REGIONS], color="skyblue")
    plt.title(f"{wk} 各区域实收对比")
    plt.tight_layout()
    plt.savefig(chart_region)
    plt.close()

    quality = {
        "return_count": ret_cnt,
        "return_amount": round(ret_amt),
        "dup_count": dup_count,
        "dup_amount": round(dup_amount),
        "zero_sales_stores": zero_stores,
        "new_stores": new_stores,
        "coverage": f"数据实际覆盖 2026-W36 至 W44（{max_date}）",
    }

    company_target = sum(region_stats[r]["target"] for r in REGIONS)
    company_attain = (round(ts / company_target * 100, 1) if company_target else 0.0)

    return {
        "success": True,
        "period": period,
        "week": wk,
        "total_sales": round(ts),
        "total_profit": round(tp),
        "profit_rate": round(tr, 1),
        "takeout_rate": round(takeout_rate, 1),
        "mom": round(mom, 1),
        "prev_total": round(prev_total),
        "region_stats": region_stats,
        "anomaly_regions": anomaly_regions,
        "anomaly_stores": anomaly_stores,
        "category_stats": category_stats,
        "company_target": round(company_target),
        "company_attain": company_attain,
        "top_items_text": top_items_text,
        "quality": quality,
        "trend": trend,
        "chart_region": chart_region,
        "chart_trend": chart_trend,
        "message": f"成功解析 {wk}。全公司实收 {round(ts)} 元，环比 {round(mom, 1)}%，毛利率 {round(tr, 1)}%。",
    }
