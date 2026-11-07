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

def submit_to_review():
    task = st.session_state.task
    task["status"] = "人工审核中"
    # 把大模型写的文字存进记忆库，供审核页面展示
    task["draft_report"] = st.session_state.get("current_real_text","")
    #清空之前的退回意见
    task["review_feedback"] = ""
    task["event_log"].append({"event":"执行完成","msg":"已生成word并提交审核"})


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
            st.session_state.qc_logs = []
            

            # 网页展示图表
            if result.get("chart_path") and os.path.exists(result["chart_path"]):
                st.image(result["chart_path"], caption="各门店实收对比", use_container_width=True)
            if result.get("chart_path_2") and os.path.exists(result["chart_path_2"]):
                st.image(result["chart_path_2"],caption="Top5商品销量对比", use_container_width=True)

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
            base_prompt = f"""
            你现在的岗位是：{emp_config.get('role', '数据分析师')}
            
            请你绝对遵守以下注意事项：
            {rules_text}
            
            【本周真实经营数据】：
            统计周期：{task['form']['period']}
            门店数量：{result['store_count']} 家
            总实收金额：{result['total_sales']} 元
            毛利：{result['total_profit']} 元
            毛利率：{result['profit_rate']}%
            
            【本周销量 Top 5 单品】：
            {result['top_items_text']}
            
            【本阶段开会纪要】：
            {meeting_text}
            
            【赛方强制排版要求（极其重要，不符合将被打回）】：
            1. 第一部分必须是“# 一、本周摘要”。要求：不超过 5 句话，必须讲清楚总实收、毛利率、最重要的1-2个异常。
            2. 第二部分必须是“# 二、核心指标表”。要求：用 Markdown 表格展示（包含 总实收、毛利率 等指标）。
            3. 第三部分必须是“# 三、单品与品类表现”。要求：结合 Top 5 单品数据进行业务分析。
            4. 第四部分必须是“# 四、异常与原因分析”。要求：必须结合会议纪要来解释异常。如果纪要没提，写“原因待核实”，绝不能瞎编！
            5. 第五部分必须是“# 五、下周关注事项”。要求：列出不超过 5 条风险点。
            """
            #=============检查是否有退回意见？===========================
            feedback = task.get("review_feedback","")
            if feedback:
                base_prompt += f"\n\n【审核人退回意见（必须优先修改）】：\n{feedback}\n请务必针对上述意见进行修改！"
            #============核心：带自动质检的重试循环================
            from tools.qc_check import check_report_quality

            max_retries = 3
            retry_count = 0
            qc_passed = False
            real_text = ""
            qc_msg=""

            st.write("⏳ 正在呼叫大模型并自动质检...")

            while retry_count < max_retries and not qc_passed:
                current_prompt = base_prompt
                if retry_count > 0:
                    current_prompt +=f"\n【警告！】你上次生成的报告存在以下问题：{qc_msg}，请务必修正！"

                real_text = call_deepseek(current_prompt)

                if real_text.startswith("❌"):
                    st.error(real_text)
                    break
                #自动质检
                qc_passed, qc_msg = check_report_quality(real_text,result["total_sales"])

                if not qc_passed:
                    retry_count +=1
                    st.session_state.qc_logs.append(f"第{retry_count}次质检失败：{qc_msg}")
                    st.warning(f"⚠️ 自动质检未通过（第 {retry_count} 次）：{qc_msg}。正在打回重写...")
                else:
                    st.session_state.qc_logs.append("最终质检通过")
                    st.success("✅ 自动质检通过！大模型生成完毕。")
            if not qc_passed:
                st.error("❌ 质检连续3次未通过，任务已强制暂停，转人工处理。")
                task["status"] = next_status(STATUS_EXECUTING, "异常中止转人工")
                log_event("质检失败", "连续3次未通过质检，转人工")
                st.rerun()
                st.stop()  # 停止运行后面的代码


        else:
            real_text = f"# 读取失败\n{result['message']}"
            st.error(result["message"])
            st.stop()
        # 生成 Word
        out_file = "本周经营周报.docx"
        chart_list = []
        if result.get("chart_path") and os.path.exists(result["chart_path"]):
            chart_list.append(result["chart_path"])
        if result.get("chart_path_2") and os.path.exists(result["chart_path_2"]):
            chart_list.append(result["chart_path_2"])

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
        st.session_state.current_real_text = real_text
        # 提交人工审核按钮
        st.button("✅ 提交人工审核", on_click=submit_to_review)

    # =========处理“人工审核中”的状态=========
    elif task["status"] == "人工审核中":
        st.warning("⚠️ 当前状态：【人工审核中】")
        st.info("请审核下方报告，确认无误后通过，或填写意见退回重写")

        #从记忆库里把大模型生成的文字拿出来
        report_content = task.get("draft_report","暂无报告内容，请退回重写。")

        #展示报告内容
        st.text_area("大模型生成的最新周报草稿",value=report_content,height=400,disabled=True)
        st.divider()

        #填写退回意见
        reject_reason = st.text_input("退回修改意见（如果是通过，请留空）：",placeholder="例如：华东区下滑原因没写清楚，请结合纪要补充。")
        col1,col2 = st.columns(2)
        with col1:
            if st.button("✅ 审核通过并交付"):
                task["status"] = next_status("人工审核中","审核通过")
                log_event("审核通过","任务已交付")
                st.success("✅ 审核通过！任务已交付。")
                st.rerun()
        with col2:
            if st.button("❌ 退回修改"):
                if not reject_reason.strip():
                    st.error("退回修改必须写具体意见！")
                else:
                    task["status"] = next_status("人工审核中","审核退回")
                    # 把意见存进记忆库，供大模型重写时读取
                    task["review_feedback"] = reject_reason
                    log_event("审核退回",f"审核意见:{reject_reason}")
                    st.warning(f"已退回，意见已记录：{reject_reason}")
                    st.rerun()
    #================处理“失败转人工”的状态
    elif task["status"] == "失败转人工":
        st.error("❌ 任务执行异常，已强制暂停并转入人工处理。")
        st.info("大模型多次未能通过自动质检，或工具调用发生异常。请人工介入。")

        st.subheader("人工救援与兜底")
        st.info("您可以手动编写最终报告，然后点击下方按钮强制交付。")

        # 1. 允许人工输入报告
        manual_report = st.text_area("请在此处输入最终报告（支持 Markdown 格式）：", height=300)

        # 2. 强制交付按钮（注意：这里必须要有 if st.button 判断！）
        if st.button("✅ 人工确认并强制交付"):
            if not manual_report.strip():
                st.warning("请输入内容后再强制交付！")
            else:
                from tools.generate_word import generate_word

                out_file = "人工兜底经营周报.docx"
                try:
                    # 直接调用 Word 工具，不再经过大模型
                    generate_word(
                        report_text=manual_report,
                        out_path=out_file,
                        title="智能经营周报(人工兜底版)",
                        meta={"统计周期": task['form'].get('period', '')}
                    )

                    # 展现下载按钮
                    with open(out_file, "rb") as f:
                        st.download_button(
                            label="📥 点击下载 人工兜底版 Word",
                            data=f,
                            file_name="人工兜底经营周报.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )

                    # 状态流转
                    task["status"] = "已交付"
                    log_event("人工交付", "由于大模型异常，审核员手动生成了报告。")
                    st.success("✅ 已强制交付！")
                    st.rerun()
                except Exception as e:
                    st.error(f"生成 Word 失败：{e}")

        st.divider()

        # 3. 放弃当前任务，重新发起
        if st.button("↺ 放弃当前任务，重新发起"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
    #=================处理"已交付"的状态===========
    elif task["status"] == "已交付":
        st.success("🎉 任务已成功交付！")
        st.balloons()

        st.info("可以下载最终生成的经营周报 Word 文档。")

        #检查是否存在人工兜底生成的文件，如果有，就展示下载按钮
        if os.path.exists("人工兜底经营周报.docx"):
            with open("人工兜底经营周报.docx", "rb") as f:
                st.download_button(
                    label="📥 点击下载 人工兜底版 Word",
                    data=f,
                    file_name="人工兜底经营周报.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
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

with st.expander("质检记录"):
    if 'qc_logs' in st.session_state and st.session_state.qc_logs:
        for log in st.session_state.qc_logs:
            st.write(f"-{log}")
    else:
        st.write("(本轮任务暂无质检记录)")


# st.session_state.task 长这样
# {
#     "status": "人工审核中",  # 当前走到哪一步
#     "form": {"period": "2026年第45周", "sales_file": "test.xlsx", ...}, # 用户传的表单
#     "event_log": [...],      # 日志记录
#     "draft_report": "这是大模型写的报告内容...", # 草稿（执行完才有）
#     "review_feedback": "退回意见"               # 意见（退回时才有）
# }

#启动网页的命令：python -m streamlit run src/app.py