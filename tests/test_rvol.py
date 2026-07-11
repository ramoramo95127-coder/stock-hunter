from stock_hunter.intraday.rvol import calculate_rvol, is_accelerating


def test_rvol_uses_same_minute_baseline() -> None:
    baseline, rvol = calculate_rvol(400_000, [100_000, 120_000, 80_000, 100_000])
    assert baseline == 100_000
    assert rvol == 4.0


def test_rvol_missing_baseline_is_explicit() -> None:
    assert calculate_rvol(100_000, []) == (None, None)


def test_volume_acceleration_requires_three_rising_minutes() -> None:
    assert is_accelerating([100, 140, 200])
    assert not is_accelerating([100, 220, 200])
    assert not is_accelerating([100, 200])
