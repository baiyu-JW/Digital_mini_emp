"""迷你数字员工 - 任务状态机（赛题基础必做项）

设计要点（对应赛题评审四词：可控 / 可用 / 懂业务 / 工程素养）：
- 状态流转表 TRANSITIONS：表驱动，可直接粘进技术报告当"状态流转表"。
- 非法流转拒绝：is_valid_transition() 查表，next_status() 作为程序判定的最后一道关。
- 关键控制由程序判定，不交给模型决定（赛题硬性要求）。
- 补料恢复 / 审核退回重做 / 异常转人工 均已闭环。
"""

# ---------------- 状态 ----------------
STATUS_PENDING = "待发起"          # 任务表单未提交
STATUS_CHECKING = "准入校验中"      # 已提交，正在校验材料
STATUS_WAITING = "等待补充材料"     # 材料缺失，暂停等补充
STATUS_EXECUTING = "执行中"         # 调用工具 + 大模型生成
STATUS_QC = "自动质检中"            # 生成物质检（可自动修正后重试）
STATUS_REVIEW = "人工审核中"        # 等待审核人通过 / 退回
STATUS_DELIVERED = "已交付"         # 审核通过，交付完成
STATUS_FAILED = "失败转人工"        # 工具/模型反复失败或超限，转人工处理

# ---------------- 事件 ----------------
E_SUBMIT = "提交表单"
E_MATERIAL_OK = "材料齐全"
E_MATERIAL_MISSING = "缺少材料"
E_RESUPPLY = "补充材料"
E_EXEC_DONE = "执行完成"
E_QC_PASS = "质检通过"
E_QC_FAIL = "质检不通过"
E_APPROVE = "审核通过"
E_REJECT = "审核退回"
E_ABORT = "异常中止转人工"          # 工具/模型重试超限时触发

# ---------------- 状态流转表（表驱动，可直接进报告）----------------
# key: 当前状态 -> {事件: 下一状态}
TRANSITIONS = {
    STATUS_PENDING: {
        E_SUBMIT: STATUS_CHECKING,
    },
    STATUS_CHECKING: {
        E_MATERIAL_OK: STATUS_EXECUTING,
        E_MATERIAL_MISSING: STATUS_WAITING,
    },
    STATUS_WAITING: {
        E_RESUPPLY: STATUS_CHECKING,        # 补料后重新准入校验
    },
    STATUS_EXECUTING: {
        E_EXEC_DONE: STATUS_QC,
        E_ABORT: STATUS_FAILED,             # 工具/模型重试超限 -> 转人工
    },
    STATUS_QC: {
        E_QC_PASS: STATUS_REVIEW,
        E_QC_FAIL: STATUS_EXECUTING,        # 自动修正后重做（多次失败由调用方判定转 FAILED）
        E_ABORT: STATUS_FAILED,
    },
    STATUS_REVIEW: {
        E_APPROVE: STATUS_DELIVERED,        # 审核通过 -> 交付
        E_REJECT: STATUS_EXECUTING,         # 退回 -> 重做（意见作为上下文传入）
    },
    # STATUS_DELIVERED / STATUS_FAILED 为终态，无出边
}


def is_valid_transition(current, event):
    """查表判断当前状态能否响应某事件。

    返回 (ok: bool, next_status: str | None)。
    赛题要求"非法流转应被拒绝"——此函数是程序判定入口。
    """
    nxt = TRANSITIONS.get(current, {}).get(event)
    if nxt is None:
        return False, None
    return True, nxt


def next_status(current, event):
    """执行流转。非法流转抛 ValueError（程序拒绝，并应由调用方记日志留痕）。

    调用方流程建议：
        先 is_valid_transition 预判 -> 合法才调 next_status；
        next_status 作为最后一道关，防止任何绕过。
    """
    ok, nxt = is_valid_transition(current, event)
    if not ok:
        raise ValueError(f"非法操作！当前状态【{current}】不能响应事件【{event}】")
    return nxt


# 供报告/界面使用的"可读流转表"
def transitions_for_report():
    rows = []
    for cur, evs in TRANSITIONS.items():
        for ev, nxt in evs.items():
            rows.append((cur, ev, nxt))
    return rows
