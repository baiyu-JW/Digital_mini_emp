from state_machine import next_status, STATUS_PENDING, STATUS_CHECKING

print("--- 测试 1：正常流转 ---")
result_1 = next_status(STATUS_PENDING, "提交表单")
print("流转后的状态是：", result_1)

print("\n--- 测试 2：非法流转 ---")
try:
    result_2 = next_status(STATUS_PENDING, "直接开始干活")
    print("流转后的状态是：", result_2)
except ValueError as e:
    print("拦截成功！错误提示：", e)