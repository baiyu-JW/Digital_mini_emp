"""文档生成工具：把周报文本生成带格式的 Word（赛题场景 A 交付物）。

设计原则（对应赛题"工程加固"加分）：
- 入参/出参明确，失败抛自定义异常而非静默。
- 写文件基于 out_path 确定性命名，重复调用覆盖同一文件（幂等，不产生一堆副本）。
"""
from pathlib import Path
from docx import Document


class WordGenError(Exception):
    """Word 生成失败的统一异常。"""


def generate_word(report_text, out_path, title="经营周报", charts=None, meta=None):
    """生成带格式的 Word 周报。

    入参:
        report_text (str): 周报正文。按换行拆段落；以 '#' 开头的行当作 Markdown 标题。
        out_path (str):     输出 .docx 路径（父目录自动创建）。
        title (str):        文档主标题。
        charts (list[str]|None): 图表 png 绝对路径列表（存在则追加）。
        meta (dict|None):   元信息，如 {"统计周期": "2026年第44周"}，写入首段斜体。
    出参:
        str: 实际写出的文件路径。
    异常:
        WordGenError: 任何写出/渲染失败。
    """
    if not report_text or not report_text.strip():
        raise WordGenError("report_text 为空，无法生成周报")

    try:
        # 1. 创建一个空白的 Word 文档
        doc = Document()

        # 2. 添加文档主标题 (level=0 代表最大的标题)
        doc.add_heading(title, level=0)

        # 3. 写入元信息（比如统计周期），并设为斜体
        if meta:
            for k, v in meta.items():
                p = doc.add_paragraph()
                run = p.add_run(f"{k}：{v}")
                run.italic = True

        # 4. 解析正文内容（智能识别 Markdown 标题）
        for block in report_text.split("\n"):
            block = block.strip()
            if not block:
                continue

            # 如果这行以 # 开头，就当作标题处理
            if block.startswith("#"):
                # 计算有几个 #，最多允许 3 级标题
                level = min(block.count("#", 0, 6), 3) or 1
                doc.add_heading(block.lstrip("#").strip(), level=level)
            else:
                # 否则就当作普通段落写入
                doc.add_paragraph(block)

        # 5. 插入图表（如果传了图片路径）
        if charts:
            for c in charts:
                if c and Path(c).exists():
                    # 可以在图片上面加个居中说明，但简单插入已经足够
                    doc.add_picture(c)

        # 6. 保存文件（如果父目录不存在，自动创建）
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(out)

        # 返回保存的文件路径
        return str(out)

    except WordGenError:
        # 如果是自己抛的错，直接放行
        raise
    except Exception as e:
        # 拦截底层意料之外的错误，包装成统一异常抛出
        raise WordGenError(f"Word 生成失败：{e}") from e