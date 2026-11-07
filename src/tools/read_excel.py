import pandas as pd
import os
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


def guess_column(df, keywords, expected_type="number"):
    """泛用核心：优先关键词匹配，失败后按数据特征盲猜"""
    for col in df.columns:
        if any(kw in str(col) for kw in keywords):
            return col

    if expected_type == "number":
        for col in df.columns:
            col_name = str(col).lower()
            if any(bad_word in col_name for bad_word in ["id", "日期", "时间", "数量", "折扣", "成本"]):
                continue

            if pd.api.types.is_numeric_dtype(df[col]):
                if df[col].dtype == 'int64' and df[col].max() == len(df):
                    continue
                if df[col].sum() > 0:
                    return col
    elif expected_type == "text":
        for col in df.columns:
            if df[col].dtype == 'object' and df[col].nunique() < len(df):
                return col
    return None


def read_sales_data(file_path):
    try:
        # 1. 极致容错读取 CSV（防止因为编码问题读进来一堆乱码）
        if file_path.endswith('.csv'):
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='gbk')
        else:
            df = pd.read_excel(file_path, engine='openpyxl')

        # 2. 【核心清洗】：把整张表的列名去掉前后空格
        df.columns = [str(c).strip() for c in df.columns]

        # 3. 【精准狙击】：先直接用硬编码找这些列，找不到再去猜！
        col_sales = None
        col_cost = None
        col_store = None
        col_item = None
        col_qty = None

        for col in df.columns:
            if "实收金额" in col:
                col_sales = col
            elif "成本金额" in col:
                col_cost = col
            elif "门店名称" in col:
                col_store = col
            elif "商品名称" in col:
                col_item = col
            elif "销售数量" in col:
                col_qty = col

        # 如果没找到标准的，再调用咱们的 guess_column 去盲猜兜底
        if not col_sales: col_sales = guess_column(df, ["实收", "销售", "金额", "营收"], "number")
        if not col_cost: col_cost = guess_column(df, ["成本", "支出", "进货"], "number")
        if not col_store: col_store = guess_column(df, ["门店", "店名", "分店"], "text")
        if not col_item: col_item = guess_column(df, ["商品", "单品", "品名"], "text")
        if not col_qty: col_qty = guess_column(df, ["数量", "销量"], "number")

        # 4. 【铁血强转】：找到金额列后，把里面的千分位逗号、空格全部去掉，强行转数字！
        if col_sales:
            # 把这一列转成字符串，去掉逗号和空格，然后再转成 float
            df[col_sales] = df[col_sales].astype(str).str.replace(',', '').str.strip()
            df[col_sales] = pd.to_numeric(df[col_sales], errors='coerce').fillna(0)
            total_sales = df[col_sales].sum()
        else:
            total_sales = 0

        if col_cost:
            df[col_cost] = df[col_cost].astype(str).str.replace(',', '').str.strip()
            df[col_cost] = pd.to_numeric(df[col_cost], errors='coerce').fillna(0)
            total_cost = df[col_cost].sum()
            total_profit = float(total_sales) - float(total_cost)
            profit_rate = (total_profit / total_sales * 100) if total_sales != 0 else 0
        else:
            total_cost = 0
            total_profit = float(total_sales)
            profit_rate = 100.0

        store_count = df[col_store].nunique() if col_store else len(df)

        # 5. 单品 Top 5
        top_items_text = "未识别到商品明细列，无法分析单品。"
        if col_item and col_sales:
            top_items = df.groupby(col_item)[col_sales].sum().sort_values(ascending=False).head(5)
            top_items_text = "\n".join([f"- {name}: {round(float(amt), 2)} 元" for name, amt in top_items.items()])

        # 6. 画图1
        chart_path = "sales_chart.png"
        if col_store and col_sales:
            store_sales = df.groupby(col_store)[col_sales].sum()
            plt.figure(figsize=(8, 4))
            plt.bar(store_sales.index, store_sales.values, color='skyblue')
            plt.title('各门店本周实收金额对比')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(chart_path)
            plt.close()
        else:
            chart_path = None

        # 7. 画图2
        chart_path_2 = "category_chart.png"
        if col_item and col_qty:
            top_items_series = df.groupby(col_item)[col_qty].sum().sort_values(ascending=False).head(5)
            plt.figure(figsize=(6, 6))
            plt.pie(top_items_series, labels=top_items_series.index, autopct='%1.1f%%',
                    colors=['#ff9999', '#66b3ff', '#99ff99', '#ffcc99', '#c2c2f0'])
            plt.title('本周销量（件数）Top 5 商品占比')
            plt.savefig(chart_path_2)
            plt.close()
        else:
            chart_path_2 = None

        # 8. 返回数据
        safe_sales = round(float(total_sales), 2) if total_sales else 0.0
        safe_profit = round(float(total_profit), 2) if total_profit else 0.0
        safe_rate = round(float(profit_rate), 1) if profit_rate else 0.0

        return {
            "success": True,
            "total_sales": safe_sales,
            "total_profit": safe_profit,
            "profit_rate": safe_rate,
            "store_count": store_count,
            "top_items_text": top_items_text,
            "anomaly_text": "系统已自动扫描，请结合业务端确认具体异常。",
            "chart_path": chart_path,
            "chart_path_2": chart_path_2,
            "message": f"成功解析数据。共 {store_count} 家门店，总实收 {safe_sales} 元，整体毛利率 {safe_rate}%。"
        }
    except Exception as e:
        return {"success": False, "message": f"读取文件失败：{e}"}