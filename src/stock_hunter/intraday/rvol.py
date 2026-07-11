from statistics import fmean


def calculate_rvol(
    current_volume: int, historical_volumes: list[int]
) -> tuple[float | None, float | None]:
    positive = [value for value in historical_volumes if value > 0]
    if not positive:
        return None, None
    baseline = fmean(positive)
    return baseline, current_volume / baseline


def is_accelerating(recent_volumes: list[int]) -> bool:
    if len(recent_volumes) < 3:
        return False
    first, second, third = recent_volumes[-3:]
    return first < second < third and third >= first * 1.5
