"""Streamlit 界面：任务发起 + 准入校验 + 缺料补充 + 执行（数据核算+大模型）+ 人工审核 + 退回重写 + 交付。

对应赛题：任务流程与人工审核、员工能力配置、工具调用、自动质检、断点恢复埋点。
"""

import streamlit as st
import os
from tools.generate_word import generate_word
from tools.read_excel import read_sales_data
from tools.call_llm import call_deepseek
from tools.read_text import read_meeting_minutes
from tools.config_loader import load_employee_config
from tools.qc_check import check_report_quality
from tools.gate import tool_call
from state_machine import (
    STATUS_PENDING, STATUS_CHECKING, STATUS_WAITING, STATUS_EXECUTING,
    E_SUBMIT, E_MATERIAL_OK, E_MATERIAL_MISSING, E_RESUPPLY,
    next_status,
)
from form_schema import check_form

st.set_page_config(page_title="智能经营周报系统", page_icon="📊")
st.title("📊 智能经营周报系统 · 迷你数字员工（场景 A）")
st.markdown(
    "请填写以下信息发起周报生成任务。系统将自动读取数据、核算指标、生成带图表的 Word 周报，"
    "并经人工审核后交付。"
)


# ---------- 任务态初始化（断点恢复基础）----------
def init_task():
    if "task" not in st.session_state:
        st.session_state.task = {"status": STATUS_PENDING, "form": {}, "event_log": []}


def log_event(ev, msg=""):
    st.session_state.task["event_log"].append({"event": ev, "msg": msg})
    # 落盘日志：失败原因持久化，页面刷新不会丢失，便于排障与演示留痕
    try:
        from datetime import datetime
        with open("app_event.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {ev}  {msg}\n")
    except Exception:
        pass


def submit_to_review():
    task = st.session_state.task
    task["status"] = "人工审核中"
    task["draft_report"] = st.session_state.get("current_real_text", "")
    task["review_feedback"] = ""


init_task()
task = st.session_state.task

emp_config = load_employee_config() or {}
limits = emp_config.get("limits", {})
max_retries = int(limits.get("max_rounds", 3))
anomaly_threshold = float(emp_config.get("anomaly_threshold", 10))


# ---------- 分支：按当前状态渲染不同界面 ----------
if task["status"] == STATUS_PENDING:
    with st.form("task_form"):
        st.subheader("任务发起")
        period = st.text_input("统计周期", placeholder="例如：2026年第44周")
        sales_file = st.file_uploader("上传销售明细", type=["xlsx", "csv"])
        meeting_file = st.file_uploader("上传周会纪要", type=["docx", "txt"])
        submitted = st.form_submit_button("提交任务")

    if submitted:
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
        if sales_file:
            with open(sales_file.name, "wb") as f:
                f.write(sales_file.getbuffer())
            task["form"]["sales_file"] = sales_file.name
        if meeting_file:
            with open(meeting_file.name, "wb") as f:
                f.write(meeting_file.getbuffer())
            task["form"]["meeting_file"] = meeting_file.name
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
        st.info("正在读取数据并核算指标，请稍候...")

        excel_path = task["form"]["sales_file"]
        period = task["form"]["period"]
        result, tool_err = tool_call("read_excel_tool", read_sales_data, excel_path, period, emp_config)
        if tool_err:
            st.error(tool_err)
            task["status"] = "失败转人工"
            log_event("工具越权/异常", tool_err)
            st.rerun()
            st.stop()

        if not result["success"]:
            st.error("❌ " + result["message"])
            task["status"] = "失败转人工"
            log_event("数据范围异常", result["message"])
            st.rerun()
            st.stop()

        st.success(result["message"])
        st.session_state.qc_logs = []
        if task.get("review_feedback"):
            st.session_state.qc_logs.append(f"【人工退回指令】{task['review_feedback']}")

        # 图表（≥2 张：区域对比 + 近4周趋势）
        for cap, key in [("各区域实收对比", "chart_region"), ("近4周全公司实收趋势", "chart_trend")]:
            p = result.get(key)
            if p and os.path.exists(p):
                st.image(p, caption=cap, use_container_width=True)

        # 可解释性面板：指标核算与异常判定过程可视化（评委必问）
        with st.expander("📊 指标核算与异常判定（可解释 / 数据溯源）"):
            st.caption("以下数字均由系统从 4 个工作表联合核算，异常阈值来自 employee.yaml（可现场修改）")
            st.json({
                "全公司": {"实收": result["total_sales"], "环比%": result["mom"],
                          "毛利率%": result["profit_rate"], "外卖占比%": result["takeout_rate"]},
                "区域": result["region_stats"],
                "异常_区域": result["anomaly_regions"],
                "异常_门店": result["anomaly_stores"],
                "数据质量": result["quality"],
                "近4周趋势": result["trend"],
            })

        meeting_path = task["form"]["meeting_file"]
        meeting_text = read_meeting_minutes(meeting_path)
        if not meeting_text or meeting_text.startswith("⚠️"):
            st.warning("⚠️ 未读取到周会纪要文本，异常原因将标注为“原因待核实”。")

        # 组装结构化数据块（喂给大模型，确保数字一致）
        region_lines = "\n".join([
            f"  {r}：实收 {rs['sales']} 元，环比 {rs['mom']}%，毛利率 {rs['profit_rate']}%，目标达成率 {rs['attain']}%"
            for r, rs in result["region_stats"].items()
        ])
        category_lines = "\n".join([
            f"  {c}：实收 {cs['sales']} 元，环比 {cs['mom']}%"
            for c, cs in result.get("category_stats", {}).items()
        ]) or "  无"
        company_attain = result.get("company_attain")
        anomaly_region_text = "\n".join([f"  {r}：环比 {m}%" for r, m in result["anomaly_regions"]]) or "  无"
        anomaly_store_text = "\n".join([f"  {n}：环比 {m}%" for n, m in result["anomaly_stores"]]) or "  无"
        q = result["quality"]
        data_block = f"""统计周期：{period}（{result['week']}）
全公司：实收 {result['total_sales']} 元，环比 {result['mom']}%，毛利率 {result['profit_rate']}%，外卖占比 {result['takeout_rate']}%{("，目标达成率 " + str(company_attain) + "%") if company_attain is not None else ""}
各区域（实收 / 环比 / 毛利率 / 目标达成率）：
{region_lines}
各品类（实收 / 环比）：
{category_lines}
异常（环比波动超 {anomaly_threshold}%）：
  区域：
{anomaly_region_text}
  门店：
{anomaly_store_text}
Top5 单品：
{result['top_items_text']}
数据质量：退货 {q['return_count']} 笔、合计 {q['return_amount']} 元（已冲减）；去除重复记录 {q['dup_count']} 条（{q['dup_amount']} 元）；覆盖范围：{q['coverage']}"""

        prompt = f"""你现在的岗位是：{emp_config.get('role', '数据分析师')}
请绝对遵守以下注意事项：
{chr(10).join(['- ' + c for c in emp_config.get('constraints', [])])}

【本周真实经营数据（已由系统核算，所有数字以数据为准，不得编造；数据不一致处以数据为准并标注）】：
{data_block}

【本阶段周会纪要】：
{meeting_text}

【赛方强制排版要求（不符合将被打回）】：
# 一、本周摘要
不超过 5 句话，讲清楚总实收、环比、毛利率、目标达成情况，以及最重要的 1~2 个异常。
# 二、核心指标表
用 Markdown 表格展示：全公司及四个区域（华东 / 华南 / 华北 / 西南）的 实收、环比、毛利率、目标达成率。
# 三、品类表现
各品类实收与环比（严格依据上方数据块“各品类”段落如实填写，不得写“数据未提供”）；本周实收前 5 名单品。
# 四、异常与原因分析
逐条列出环比波动超过 ±{anomaly_threshold}% 的区域与门店（见上方“异常”），结合周会纪要解释原因并注明周次；
纪要没提到的写“原因待核实”，绝不瞎编；纪要说法与数据不一致时以数据为准并指出。
# 五、数据质量说明
说明本周退货、重复记录处理、缺失 / 新开 / 停业门店等情况。
# 六、下周关注事项
来自纪要行动项或数据风险点，不超过 5 条。

【约束】仅输出上述允许指标，不写客单价、同比等数据不支持的内容；所有数字必须来自上方数据块。"""

        feedback = task.get("review_feedback", "")
        if feedback:
            prompt += f"\n\n【审核人退回意见（必须优先修改）】：\n{feedback}\n请务必针对意见修改！"

        retry = 0
        qc_passed = False
        real_text = ""
        qc_msg = ""
        while retry < max_retries and not qc_passed:
            cur = prompt
            if retry > 0:
                cur += f"\n【警告！】你上次生成的报告存在以下问题：{qc_msg}，请务必修正！"
            real_text = call_deepseek(cur, emp_config)
            if real_text.startswith("❌"):
                st.error(real_text)
                task["status"] = "失败转人工"
                log_event("模型异常", real_text)
                st.stop()
            qc_passed, qc_msg = check_report_quality(real_text, result, emp_config)
            if not qc_passed:
                retry += 1
                st.session_state.qc_logs.append(f"第{retry}次质检失败：{qc_msg}")
                st.warning(f"⚠️ 自动质检未通过（第 {retry} 次）：{qc_msg}。正在打回重写...")
            else:
                st.session_state.qc_logs.append("最终质检通过")
                st.success("✅ 自动质检通过！大模型生成完毕。")

        if not qc_passed:
            st.error("❌ 质检连续未通过，任务已强制暂停，转人工处理。")
            task["status"] = "失败转人工"
            log_event("质检失败", f"连续 {max_retries} 次未通过，最后一次原因：{qc_msg}")
            st.rerun()
            st.stop()

        # 生成 Word
        out_file = "本周经营周报.docx"
        chart_list = [result[k] for k in ("chart_region", "chart_trend")
                      if result.get(k) and os.path.exists(result[k])]
        try:
            generate_word(
                report_text=real_text, out_path=out_file, title="智能经营周报",
                meta={"统计周期": period}, charts=chart_list,
            )
            with open(out_file, "rb") as f:
                task["word_data"] = f.read()
            task["word_filename"] = "本周经营周报.docx"
            st.download_button(
                label="📥 点击下载 Word 经营周报（预览）", data=task["word_data"],
                file_name=task["word_filename"],
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception as e:
            st.error(f"生成 Word 失败：{e}")

        st.session_state.current_real_text = real_text
        st.button("✅ 提交人工审核", on_click=submit_to_review)

    # =========处理“人工审核中”的状态=========
    elif task["status"] == "人工审核中":
        st.warning("⚠️ 当前状态：【人工审核中】")
        st.info("请审核下方报告，确认无误后通过，或填写意见退回重写。")
        report_content = task.get("draft_report", "暂无报告内容，请退回重写。")
        st.text_area("大模型生成的最新周报草稿", value=report_content, height=400, disabled=True)
        st.divider()
        reject_reason = st.text_input(
            "退回修改意见（如果是通过，请留空）：",
            placeholder="例如：华东区下滑原因没写清楚，请结合纪要补充。",
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 审核通过并交付"):
                task["status"] = next_status("人工审核中", "审核通过")
                task["delivered_by"] = "ai"
                log_event("审核通过", "任务已交付")
                st.success("✅ 审核通过！任务已交付。")
                st.rerun()
        with col2:
            if st.button("❌ 退回修改"):
                if not reject_reason.strip():
                    st.error("退回修改必须写具体意见！")
                else:
                    task["status"] = next_status("人工审核中", "审核退回")
                    task["review_feedback"] = reject_reason
                    log_event("审核退回", f"审核意见:{reject_reason}")
                    st.warning(f"已退回，意见已记录：{reject_reason}")
                    st.rerun()

    # ================处理“失败转人工”的状态================
    elif task["status"] == "失败转人工":
        st.error("❌ 任务执行异常，已强制暂停并转入人工处理。")
        st.info("大模型多次未能通过自动质检，或工具/数据调用发生异常。请人工介入。")
        # 直接展示失败原因（最近事件），避免排查时被页面刷新掩盖
        if task["event_log"]:
            st.subheader("本次失败原因（事件日志）")
            for e in task["event_log"][-6:]:
                st.write(f"- **{e['event']}**  {e['msg']}")
        st.subheader("人工救援与兜底")
        st.info("您可以手动编写最终报告，然后点击下方按钮强制交付。")
        manual_report = st.text_area("请在此处输入最终报告（支持 Markdown 格式）：", height=300)
        if st.button("✅ 人工确认并强制交付"):
            if not manual_report.strip():
                st.warning("请输入内容后再强制交付！")
            else:
                out_file = "人工兜底经营周报.docx"
                try:
                    generate_word(
                        report_text=manual_report, out_path=out_file,
                        title="智能经营周报(人工兜底版)", meta={"统计周期": task['form'].get('period', '')},
                    )
                    with open(out_file, "rb") as f:
                        task["word_data"] = f.read()
                    task["word_filename"] = "人工兜底经营周报.docx"
                    task["status"] = "已交付"
                    task["delivered_by"] = "human"
                    log_event("人工交付", "由于大模型异常，审核员手动生成了报告。")
                    st.success("✅ 已强制交付！")
                    st.rerun()
                except Exception as e:
                    st.error(f"生成 Word 失败：{e}")
        st.divider()
        if st.button("↺ 放弃当前任务，重新发起"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # =================处理"已交付"的状态===========
    elif task["status"] == "已交付":
        st.success("🎉 任务已成功交付！")
        st.balloons()
        st.info("可以下载最终生成的经营周报 Word 文档。")
        word_data = task.get("word_data")
        word_name = task.get("word_filename", "经营周报.docx")
        if word_data:
            st.download_button(
                label=f"📥 点击下载 {word_name}", data=word_data, file_name=word_name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        else:
            st.warning("⚠️ 未在记忆库找到生成的报告文件，请重置后重新生成。")

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
    if "qc_logs" in st.session_state and st.session_state.qc_logs:
        for log in st.session_state.qc_logs:
            st.write(f"- {log}")
    else:
        st.write("(本轮任务暂无质检记录)")
