import pandas as pd
import os
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
def read_sales_data(file_path):

    """
        工具：读取销售明细 Excel，并计算关键数据。
        入参：file_path (用户上传的 Excel 文件路径)
        出参：一个字典，包含销售额、环比等真实数据。
        """
    """
    工具：读取销售明细 Excel，计算关键数据，并生成柱状图。
    """
    try:
        df = pd.read_excel(file_path)
        #清洗数据
        if "销售额" in df.columns:
            # 强制把这一列转换成数字（遇到文字就变成空值），然后再求和
            df["销售额"] = pd.to_numeric(df["销售额"],errors="coerce").fillna(0)
            total_sales = df["销售额"].sum()
        else:
            total_sales = 0

        store_count = len(df)
        # ================= 核心绝活：画图 =================
        chart_path = "sales_chart.png" # 图片保存的名字
        # 只有存在“门店”和“销售额”两列时才画图
        if "门店" in df.columns and "销售额" in df.columns:
            plt.figure(figsize=(8,4))
            plt.bar(df["门店"],df["销售额"],color="skyblue")
            plt.xlabel('门店名称')
            plt.ylabel('销售额(元)')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(chart_path)
            plt.close()
        #============================================

        return{
            "success": True,
            "total_sales":total_sales,
            "store_count":store_count,
            "chart_path":chart_path,
            "message":f"成功读取{store_count}条门店数据，总销售额{total_sales}"
        }
    except Exception as e:
        return{
            "success":False,
            "total_sales":0,
            "store_count":0,
            "message":f"读取Excel失败：{e}"
        }




