from semiskill.governance.policy import tool_risk


def test_allowlisted_tool_is_clean():
    assert tool_risk("Read") == 0.0
    assert tool_risk("Grep") == 0.0


def test_dangerous_tool_is_hardfail_severity():
    assert tool_risk("Bash") >= 0.9
    assert tool_risk("Exec") >= 0.9


def test_unknown_tool_is_moderate():
    assert 0.0 < tool_risk("SomeCustomTool") < 0.9
