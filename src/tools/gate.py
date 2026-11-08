"""工具调用网关（赛题工程加固加分项）。

赛题要求：员工只能调用为其开放的工具；越权调用应被拒绝并留痕。
本网关从 employee.yaml 的 allowed_tools 白名单校验，所有工具调用经此入口。
"""
import logging
from tools.config_loader import load_employee_config

logger = logging.getLogger("tool_gate")


def tool_call(tool_name, func, *args, **kwargs):
    """受控调用工具。

    入参:
        tool_name (str): 工具名，须在 employee.yaml allowed_tools 白名单内。
        func: 实际工具函数。
    出参:
        (result, error): 成功时 error=None；被拒/异常时 result=None、error 为 ❌ 开头字符串。
    """
    cfg = load_employee_config() or {}
    allowed = cfg.get("allowed_tools", [])
    if tool_name not in allowed:
        msg = f"越权调用被拒绝：{tool_name} 不在员工开放工具列表 {allowed}"
        logger.warning(msg)
        return None, "❌ " + msg
    try:
        return func(*args, **kwargs), None
    except Exception as e:  # noqa: BLE001
        msg = f"工具 {tool_name} 执行异常：{e}"
        logger.error(msg)
        return None, "❌ " + msg
