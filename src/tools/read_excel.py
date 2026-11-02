import pandas as pd
def read_sales_data(file_path):
    """
        工具：读取销售明细 Excel，并计算关键数据。
        入参：file_path (用户上传的 Excel 文件路径)
        出参：一个字典，包含销售额、环比等真实数据。
        """
    try:
        df = pd.read_excel(file_path)

        if "销售额" in df.columns:
            # 强制把这一列转换成数字（遇到文字就变成空值），然后再求和
            total_sales = pd.to_numeric(df["销售额"], errors='coerce').sum()
        else:
            total_sales = df.select_dtypes(include=['number']).sum().sum()

        store_count = len(df)
        return{
            "success": True,
            "total_sales":total_sales,
            "store_count":store_count,
            "message":f"成功读取{store_count}条门店数据，总销售额{total_sales}"
        }
    except Exception as e:
        return{
            "success":False,
            "total_sales":0,
            "store_count":0,
            "message":f"读取Excel失败：{e}"
        }




