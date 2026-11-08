# 迷你数字员工 · 经营周报员工（赛题场景 A）

一个"可审核、可交付"的岗位业务 Agent：读取门店销售数据与周会纪要，核算核心指标、识别异常波动、生成带图表的经营周报 Word，经人工审核后交付；材料缺失/工具故障/超限时暂停说明，不编造、不崩溃。

## 技术栈

- **语言/界面**：Python 3.10+、Streamlit（轻量 Web 界面，免写前端）
- **数据核算**：pandas + openpyxl（读取 Excel 4 个工作表并联合计算）
- **文档生成**：python-docx（带格式 Word）+ matplotlib（图表）
- **大模型**：DeepSeek（兼容 OpenAI 接口；切换 GLM 仅需改 `src/tools/call_llm.py` 的 model/url）
- **流程控制**：自研状态机（`src/state_machine.py`，表驱动），关键控制由程序判定（赛题不强制 LangGraph）

## 一键运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置密钥（切勿提交 .env）
cp .env.example .env
# 编辑 .env，填入：DEEPSEEK_API_KEY=你的key

# 3. 启动（自动打开浏览器，默认 http://localhost:8501）
python main.py
# 或： streamlit run src/app.py
```

## 目录结构

```
Digital_mini_emp/
├── main.py                  # 启动器（自动选端口 + 开浏览器）
├── employee.yaml            # ★员工能力配置（岗位/步骤/阈值/limits，业务人员可改）
├── requirements.txt
├── .env.example             # 密钥模板
├── 数据说明.md / 周报格式要求.md / 公开样例用例.md   # 赛题数据包（自测对标）
├── src/
│   ├── app.py               # Streamlit 界面（流程编排 + 人工审核 + 退回）
│   ├── state_machine.py     # 状态流转表 + 非法流转拒绝（可控核心）
│   ├── form_schema.py       # 表单校验（缺料判定）
│   └── tools/
│       ├── read_excel.py    # 数据读取与核算（四表 join：实收/环比/达成率/外卖占比/异常/质量）
│       ├── read_text.py     # 会议纪要读取
│       ├── call_llm.py      # 大模型调用（读取 limits.timeout_seconds）
│       ├── generate_word.py # Word 生成（幂等、图表嵌入）
│       ├── qc_check.py      # 自动质检（字数/结构/数据一致性）
│       ├── config_loader.py # 加载 employee.yaml
│       └── gate.py          # 工具越权网关（工程加固加分）
└── tests/                   # pytest：状态机 + 文档生成
```

## 评分点对应

| 赛题要求 | 本项目实现 |
|---|---|
| 流程 + 人工审核 + 状态流转表 + 非法拒绝 | `state_machine.py` 表驱动 + `app.py` 审核/退回 |
| 员工配置不写死代码 | `employee.yaml`（步骤/约束/阈值/limits 均可改） |
| ≥3 工具 + 受控 | `read_excel` / `read_text` / `generate_word` + `gate` 白名单 |
| ≥3 类自动质检 + 记录 | `qc_check.py`：字数/结构/数据一致性 + `qc_logs` |
| 缺料暂停 / 故障不崩溃不编造 | 准入校验 + 异常转人工 + 数据超范围暂停 |
| 断点恢复（加分） | `event_log` 埋点 + `st.session_state` 任务态 |
| 工程加固（加分） | 越权拒绝留痕 + Word 生成幂等 |

> 数据口径严格对齐赛题《数据说明》《周报格式要求》。公开样例用例（A-01~A-05）的数字经本系统核算逐项吻合（如 W44 全公司实收 573,635、环比 -9.3%、毛利率 61.1%、外卖占比 31.8%，四大区域与异常门店完全一致）。
