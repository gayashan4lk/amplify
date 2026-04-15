"""T083: Constitution V — no silent/generic failure message can reach the user.

`build_failure_record` must reject empty or generic `user_message` strings
for every FailureCode.
"""

from __future__ import annotations

import pytest

from models.errors import FailureCode
from services.failures import build_failure_record

GENERIC_MESSAGES = ["", "   ", "something went wrong", "an error occurred", "unknown error"]


@pytest.mark.parametrize("code", list(FailureCode))
@pytest.mark.parametrize("user_message", GENERIC_MESSAGES)
def test_generic_messages_are_rejected(code: FailureCode, user_message: str):
    with pytest.raises(ValueError):
        build_failure_record(
            code=code,
            user_message=user_message,
            suggested_action="do something concrete",
        )


@pytest.mark.parametrize("code", list(FailureCode))
def test_specific_messages_pass(code: FailureCode):
    record = build_failure_record(
        code=code,
        user_message=f"Specific description of {code.value}.",
        suggested_action="Retry later.",
    )
    assert record.code is code
    assert record.user_message.strip() != ""
