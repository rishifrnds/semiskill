from semiskill.intelligence.stability import ExecRecord, StabilityParams, evaluate_stability

P = StabilityParams()


def _rec(outcome="executed_ok", error=0.5, cost=0.0, ts=0.0):
    return ExecRecord(action="propose", outcome=outcome, error_signal=error, cost=cost, timestamp=ts)


def _eval(history, error, params=P, now=1000.0):
    return evaluate_stability(history, latest_error_signal=error, params=params, now=now)


def test_deadband_skips():
    v = _eval([], 0.02)
    assert not v.allow and v.reason == "skipped:deadband"


def test_hysteresis_blocks_below_hi_when_not_acting():
    v = _eval([], 0.08)                       # not acting, 0.08 < hi 0.10
    assert not v.allow and v.reason == "blocked:hysteresis"


def test_allows_above_hi_when_not_acting():
    assert _eval([], 0.5).reason == "allow"


def test_cooldown_blocks_recent_execution():
    params = StabilityParams(cooldown_window=100.0)
    v = _eval([_rec(ts=950.0)], 0.5, params=params, now=1000.0)   # 50s < 100s
    assert v.reason == "blocked:cooldown"


def test_circuit_breaker_trips_on_consecutive_failures():
    hist = [_rec("executed_failed", ts=i) for i in range(3)]
    assert _eval(hist, 0.5).reason == "blocked:breaker"


def test_breaker_reset_by_success():
    hist = [_rec("executed_failed", ts=0), _rec("executed_ok", ts=1), _rec("executed_failed", ts=2)]
    assert _eval(hist, 0.5).reason != "blocked:breaker"


def test_trajectory_blocks_when_not_improving():
    hist = [_rec(error=0.5, ts=i) for i in range(3)]      # flat |error|
    assert _eval(hist, 0.5).reason == "blocked:trajectory"


def test_trajectory_allows_when_improving():
    hist = [_rec(error=0.9, ts=0), _rec(error=0.6, ts=1), _rec(error=0.3, ts=2)]
    assert _eval(hist, 0.3).allow


def test_cost_blocks_spend_without_reduction():
    params = StabilityParams(trajectory_window=100)      # disable trajectory so cost is reached
    hist = [_rec(error=0.5, cost=1.0, ts=0), _rec(error=0.5, cost=1.0, ts=1)]
    assert _eval(hist, 0.5, params=params).reason == "blocked:cost"


def test_deny_precedence_deadband_first():
    hist = [_rec("executed_failed", ts=i) for i in range(5)]  # would trip breaker
    assert _eval(hist, 0.01).reason == "skipped:deadband"     # but deadband short-circuits


def test_no_oscillation_on_converging_stream():
    params = StabilityParams()
    errors = [0.9, 0.7, 0.5, 0.3, 0.15, 0.06, 0.02]
    history, verdicts = [], []
    for i, err in enumerate(errors):
        v = evaluate_stability(history, latest_error_signal=err, params=params, now=float(i))
        verdicts.append(v.reason)
        if v.allow:
            history.append(_rec(error=err, ts=float(i)))     # simulate a real correction
    assert verdicts[-1] == "skipped:deadband"                # settles, doesn't flap
    assert "blocked:hysteresis" not in verdicts              # monotone-decreasing => no flapping
