"""状态机单元测试（pytest）。

运行：在项目根目录执行  python -m pytest tests/ -q
覆盖：正常流转 / 补料恢复 / 审核退回 / 异常转人工 / 非法流转拒绝。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from state_machine import (
    STATUS_PENDING, STATUS_CHECKING, STATUS_WAITING, STATUS_EXECUTING,
    STATUS_QC, STATUS_REVIEW, STATUS_DELIVERED, STATUS_FAILED,
    E_SUBMIT, E_MATERIAL_OK, E_MATERIAL_MISSING, E_RESUPPLY, E_EXEC_DONE,
    E_QC_PASS, E_QC_FAIL, E_APPROVE, E_REJECT, E_ABORT,
    next_status, is_valid_transition,
)
import pytest


def test_pending_submit_to_checking():
    assert next_status(STATUS_PENDING, E_SUBMIT) == STATUS_CHECKING


def test_checking_material_ok_to_executing():
    assert next_status(STATUS_CHECKING, E_MATERIAL_OK) == STATUS_EXECUTING


def test_checking_material_missing_to_waiting():
    assert next_status(STATUS_CHECKING, E_MATERIAL_MISSING) == STATUS_WAITING


def test_waiting_resupply_back_to_checking():
    assert next_status(STATUS_WAITING, E_RESUPPLY) == STATUS_CHECKING


def test_executing_done_to_qc():
    assert next_status(STATUS_EXECUTING, E_EXEC_DONE) == STATUS_QC


def test_qc_pass_to_review():
    assert next_status(STATUS_QC, E_QC_PASS) == STATUS_REVIEW


def test_qc_fail_back_to_executing():
    assert next_status(STATUS_QC, E_QC_FAIL) == STATUS_EXECUTING


def test_review_approve_to_delivered():
    assert next_status(STATUS_REVIEW, E_APPROVE) == STATUS_DELIVERED


def test_review_reject_back_to_executing():
    assert next_status(STATUS_REVIEW, E_REJECT) == STATUS_EXECUTING


def test_executing_abort_to_failed():
    assert next_status(STATUS_EXECUTING, E_ABORT) == STATUS_FAILED


def test_illegal_transition_rejected():
    # 待发起状态不能直接"审核通过"
    assert is_valid_transition(STATUS_PENDING, E_APPROVE) == (False, None)
    with pytest.raises(ValueError):
        next_status(STATUS_PENDING, E_APPROVE)


def test_terminal_states_have_no_outgoing():
    assert is_valid_transition(STATUS_DELIVERED, E_APPROVE) == (False, None)
    assert is_valid_transition(STATUS_FAILED, E_APPROVE) == (False, None)
