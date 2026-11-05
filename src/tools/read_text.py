import os
def read_meeting_minutes(file_path):
    """
    工具：读取周会纪要（支持txt和docx）
    """
    try:
        if file_path.endswith(".txt"):
            with open(file_path,"r",encoding="utf-8") as f:
                return f.read()
        elif file_path.endswith(".docx"):
            from docx import Document
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
            return text
        else:
            return "无法识别的文件格式。"
    except Exception as e:
        return f"读取纪要失败：{e}"
