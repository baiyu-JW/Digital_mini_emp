"""Streamlit 界面：任务发起 + 准入校验 + 缺料补充 + 执行生成 Word。"""

import streamlit as st
import pandas as pd
from tools.generate_word import generate_word

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
        form_data = {
            "period": task.get("form", {}).get("period"),
            "sales_file": sales_file.name if sales_file else None,
            "meeting_file": meeting_file.name if meeting_file else None,
        }
        is_valid, missing = check_form(form_data)
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
        st.info("正在调用大模型生成经营周报，请稍候...")

        # 模拟的周报内容（注意文字不能缩进！）
        mock_text = f"""# 一、本周总体情况
这是 {task['form']['period']} 的经营数据汇总。
本周总销售额为 120 万元，环比上升 12%。
# 二、异常分析
华东区受台风天气影响，门店客流减少，导致销售下滑。
建议下周开展线上促销活动以弥补损失。"""

        out_file = "本周经营周报.docx"

        # 调用 Word 工具
        try:
            generate_word(
                report_text=mock_text,
                out_path=out_file,
                title="智能经营周报",
                meta={"统计周期": task['form']['period']}
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

    # 底部重置按钮（注意缩进，和 if 平级）
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