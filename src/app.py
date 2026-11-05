"""Streamlit 界面：任务发起 + 准入校验 + 缺料补充 + 执行生成 Word。"""

import streamlit as st
import pandas as pd
import os
from tools.generate_word import generate_word
from tools.read_excel import read_sales_data
from tools.call_llm import call_deepseek  # 修复了这里的拼写错误
from tools.read_text import read_meeting_minutes
from tools.config_loader import load_employee_config
from state_machine import (
    STATUS_PENDING, STATUS_CHECKING, STATUS_WAITING, STATUS_EXECUTING,
    E_SUBMIT, E_MATERIAL_OK, E_MATERIAL_MISSING, E_RESUPPLY,
    next_status,
)
from form_schema import check_form

st.set_page_config(page_title="智能经营周报系统", page_icon="📊")
st.title("📊 智能经营周报系统")
st.markdown("请填写以下信息发起周报生成任务")


# ---------- 任务态初始化（断点恢复基础）----------
def init_task():
    if "task" not in st.session_state:
        st.session_state.task = {"status": STATUS_PENDING, "form": {}, "event_log": []}


def log_event(ev, msg=""):
    st.session_state.task["event_log"].append({"event": ev, "msg": msg})


init_task()
task = st.session_state.task

# ---------- 分支：按当前状态渲染不同界面 ----------
if task["status"] == STATUS_PENDING:
    with st.form("task_form"):
        st.subheader("任务发起")
        period = st.text_input("统计周期", placeholder="例如：2026年第44周")
        sales_file = st.file_uploader("上传销售明细", type=["xlsx", "csv"])
        meeting_file = st.file_uploader("上传周会纪要", type=["docx", "txt"])
        submitted = st.form_submit_button("提交任务")

    if submitted:
        # 1) 提交 -> 准入校验中
        task["status"] = next_status(STATUS_PENDING, E_SUBMIT)
        form_data = {
            "period": period,
            "sales_file": sales_file.name if sales_file else None,
            "meeting_file": meeting_file.name if meeting_file else None,
        }

        if sales_file:
            with open(sales_file.name, "wb") as f:
                f.write(sales_file.getbuffer())
        if meeting_file:
            with open(meeting_file.name, "wb") as f:
                f.write(meeting_file.getbuffer())

        task["form"] = form_data

        # 2) 准入校验 -> 产生事件
        is_valid, missing = check_form(form_data)
        if is_valid:
            task["status"] = next_status(STATUS_CHECKING, E_MATERIAL_OK)
            log_event(E_MATERIAL_OK)
            st.success("✅ 材料齐全，状态流转至【执行中】...")
        else:
            task["status"] = next_status(STATUS_CHECKING, E_MATERIAL_MISSING)
            log_event(E_MATERIAL_MISSING, str(missing))
            st.error(f"❌ 缺少材料：{missing}")
            st.warning("⚠️ 任务已暂停，状态变为【等待补充材料】。")
        st.rerun()

elif task["status"] == STATUS_WAITING:
    st.warning("⚠️ 当前状态【等待补充材料】，请补充缺失文件后重新提交。")
    with st.form("resupply_form"):
        st.subheader("补充材料")
        sales_file = st.file_uploader("上传销售明细", type=["xlsx", "csv"])
        meeting_file = st.file_uploader("上传周会纪要", type=["docx", "txt"])
        resubmitted = st.form_submit_button("补充并提交")

    if resubmitted:
        # 不要重新打包整个表单了，直接把新文件存进记忆库
        if sales_file:
            with open(sales_file.name,"wb") as f:
                f.write(sales_file.getbuffer())
            task["form"]["sales_file"] = sales_file.name
        if meeting_file:
            with open(meeting_file.name,"wb") as f:
                f.write(meeting_file.getbuffer())
            task["form"]["meeting_file"] = meeting_file.name

        # 重新检查记忆库里的表单是否齐全
        is_valid, missing = check_form(task["form"])

        if is_valid:
            task["status"] = next_status(STATUS_WAITING, E_RESUPPLY)
            task["status"] = next_status(STATUS_CHECKING, E_MATERIAL_OK)
            log_event(E_RESUPPLY)
            log_event(E_MATERIAL_OK)
            st.success("✅ 材料补齐，状态流转至【执行中】。")
        else:
            st.error(f"❌ 仍缺少：{missing}")
        st.rerun()

else:
    # ========= 处理“执行中”的状态 =========
    if task["status"] == STATUS_EXECUTING:
        st.success("✅ 当前状态：【执行中】")
        st.info("正在读取数据并呼叫 DeepSeek 生成经营周报，请稍候...")

        excel_path = task["form"]["sales_file"]
        result = read_sales_data(excel_path)

        if result["success"]:
            st.info(result["message"])

            # 网页展示图表
            if result.get("chart_path") and os.path.exists(result["chart_path"]):
                st.image(result["chart_path"], caption="各门店销售数据", use_container_width=True)

            meeting_path = task["form"]["meeting_file"]
            meeting_text = read_meeting_minutes(meeting_path)
            st.write(f"📄 已读取会议纪要：{meeting_text[:20]}...")

            emp_config = load_employee_config()
            if emp_config:
                rules_text = "\n".join([f"-{rule}" for rule in emp_config.get("constraints",[])])
            else:
                rules_text = "无特殊要求"

            # ================= 接入大模型的核心代码 =================
            st.write("⏳ 正在呼叫大模型生成专业报告...")

            # 组装提示词（把真实数据喂给它）
            prompt = f"""
            你现在的岗位是：{emp_config.get('role', '数据分析师')}
            
            请你绝对遵守以下注意事项：
            {rules_text}
            
            请帮我写一份经营周报。
            统计周期：{task['form']['period']}
            门店数量：{result['store_count']} 家
            总销售额：{result['total_sales']} 元。
            【本阶段开会纪要如下】：
            {meeting_text}
            
            请结合以上所有数据和会议纪要，严格按照以下格式撰写一份周报：
            # 一、本周数据概况
            # 二、业务分析洞察
            # 三、下一步行动建议
            要求语言专业，字数满足配置要求。
            """

            # 调用大模型，把返回的文字存进 real_text
            real_text = call_deepseek(prompt)

            # 如果大模型报错了，给它一点兜底
            if real_text.startswith("❌"):
                st.error(real_text)
            else:
                st.success("✅ 大模型生成完毕！")
            # =======================================================

        else:
            real_text = f"# 读取失败\n{result['message']}"
            st.error(result["message"])

        # 生成 Word
        out_file = "本周经营周报.docx"
        chart_list = [result["chart_path"]] if result.get("chart_path") else None

        try:
            generate_word(
                report_text=real_text,
                out_path=out_file,
                title="智能经营周报",
                meta={"统计周期": task['form']['period']},
                charts=chart_list
            )

            # 生成下载按钮
            with open(out_file, "rb") as f:
                st.download_button(
                    label="📥 点击下载 Word 经营周报",
                    data=f,
                    file_name="本周经营周报.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
        except Exception as e:
            st.error(f"生成 Word 失败：{e}")

        # 提交人工审核按钮
        if st.button("✅ 提交人工审核"):
            task["status"] = next_status(STATUS_EXECUTING, "执行完成")
            log_event("执行完成", "已生成 Word 并提交审核")
            st.rerun()

    # ========= 其他状态（比如审核中）暂时占位 =========
    else:
        st.info(f"当前状态：【{task['status']}】。")

    # 底部重置按钮
    st.divider()
    if st.button("↺ 重置任务（演示用）"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ---------- 状态面板（放在最外层，永远显示） ----------
st.divider()
st.subheader("当前任务状态")
st.write(f"状态：**{task['status']}**")
with st.expander("事件日志（断点恢复埋点）"):
    if task["event_log"]:
        for e in task["event_log"]:
            st.write(f"- {e['event']}  {e['msg']}")
    else:
        st.write("（暂无事件）")