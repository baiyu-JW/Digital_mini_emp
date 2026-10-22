STATUS_PENDING= "待发起"
STATUS_CHECKING = "准入校验中"
STATUS_WAITING = "等待补充材料"
STATUS_EXECUTING = "执行中"

def next_status(current_status,event):
    if current_status == STATUS_PENDING and event == "提交表单":
        return STATUS_CHECKING
    elif current_status == STATUS_CHECKING:
        if event == "材料齐全":
            return STATUS_EXECUTING
        elif event == "缺少材料":
            return STATUS_WAITING
    raise ValueError(f"非法操作!当前状态是【{current_status}】,不能执行【{event}】！")

