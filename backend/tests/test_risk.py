from backend.app.risk import size_position


def test_sizing_basic():
    r = size_position(equity=10_000, entry_price=3000, stop_price=2985, risk_pct=0.01)
    # risk amount = 100, stop dist = 15, qty = 100/15 = 6.666 -> rounded down to 0.001 step
    assert r.qty > 0
    assert abs(r.qty * 15 - 100) <= 15 * 0.001  # within one qty step


def test_sizing_rejects_zero_stop():
    r = size_position(equity=10_000, entry_price=3000, stop_price=3000, risk_pct=0.01)
    assert r.qty == 0 and r.rejected_reason


def test_sizing_below_min():
    r = size_position(equity=10, entry_price=3000, stop_price=2999, risk_pct=0.001, min_qty=0.001)
    # risk amount 0.01, stop dist 1 -> qty 0.01 → fine
    # Try a smaller one:
    r2 = size_position(equity=1, entry_price=3000, stop_price=2999, risk_pct=0.0001, min_qty=0.01)
    assert r2.qty == 0 and r2.rejected_reason
