"""Unit tests for time window utilities."""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from metrics_master.windows import monday_of, week_boundaries, week_label, days_between, parse_date


def test_monday_of():
    assert monday_of(date(2025, 1, 6)) == date(2025, 1, 6)   # Monday
    assert monday_of(date(2025, 1, 8)) == date(2025, 1, 6)   # Wednesday
    assert monday_of(date(2025, 1, 12)) == date(2025, 1, 6)  # Sunday


def test_week_boundaries():
    weeks = week_boundaries(4, end=date(2025, 1, 27))
    assert len(weeks) == 4
    for mon, sun in weeks:
        assert mon.weekday() == 0
        assert sun.weekday() == 6


def test_week_label():
    assert week_label(date(2025, 1, 6)) == "Jan 6"


def test_days_between():
    assert days_between("2025-01-01", "2025-01-04") == 3.0
    assert days_between(None, "2025-01-04") is None
    assert days_between("2025-01-01", None) is None


def test_parse_date():
    dt = parse_date("2025-01-15T10:30:00.000+0000")
    assert dt is not None
    assert dt.day == 15
    assert parse_date(None) is None
    assert parse_date("") is None


if __name__ == "__main__":
    test_monday_of()
    test_week_boundaries()
    test_week_label()
    test_days_between()
    test_parse_date()
    print("All window tests passed.")
