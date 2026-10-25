import streamlit as st
from form_schema import check_form

st.set_page_config(page_title="智能经营周报系统",page_icon="📊")
st.title("📊 智能经营周报系统")
st.markdown("请填写以下信息发起周报生成任务")

with st.form("task_form"):
    st.subheader("任务发起")
    period = st.text_input("统计周期",placeholder="例如：2026年第44周")
    sales_file = st.file_uploader("上传销售明细",type=["xlsx","csv"])
    meeting_file = st.file_uploader("上传周会纪要",type=["docx","txt"])
    submitted = st.form_submit_button("提交任务")

if submitted:
    form_data = {
        "period":period,
        "sales_file":sales_file.name if sales_file else None,
        "meeting_file":meeting_file.name if meeting_file else None
    }
    is_valid,msg = check_form(form_data)

    st.divider()
    st.subheader("系统处理结果")

    if is_valid:
        st.success(f"✅{msg}")
        st.info("➡️ 下一步动作：状态流转至【执行中】，准备开始调用大模型...")
    else:
        st.error(f"❌ {msg}")
        st.warning("⚠️ 任务已暂停，状态变为【等待补充材料】。")

#页面启动方法：终端输入python -m streamlit run src/app.py
