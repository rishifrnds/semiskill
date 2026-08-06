from pathlib import Path


def test_legacy_file_based_gate_drivers_are_non_authoritative_tombstones():
    for relative in (
        "tools/gate_args.py",
        "tools/gate2_args.py",
        "tools/dv-gate.js",
        "tools/dv-gate2.js",
        "tools/dv-wave.js",
    ):
        text = Path(relative).read_text(encoding="utf-8")
        assert "RETIRED:" in text
        assert "REVIEW.json" not in text
        assert "ready:true" not in text
