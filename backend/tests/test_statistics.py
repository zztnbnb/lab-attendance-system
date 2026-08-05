from datetime import datetime, timezone

from app.services.statistics import split_duration_by_local_day


def test_cross_midnight_duration_is_split_by_shanghai_day():
    start = datetime(2026, 7, 20, 15, 30, tzinfo=timezone.utc)  # 23:30 上海
    end = datetime(2026, 7, 20, 17, 30, tzinfo=timezone.utc)  # 次日 01:30 上海
    result = split_duration_by_local_day(start, end)
    values = list(result.values())
    assert values == [1800, 5400]
    assert sum(values) == 7200
