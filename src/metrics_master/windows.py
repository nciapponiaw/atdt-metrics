"""Time window utilities — Monday-start weeks, quarter resolution from labels."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Sequence


def monday_of(d: date) -> date:
    """Return the Monday of the week containing date d."""
    return d - timedelta(days=d.weekday())


def week_boundaries(num_weeks: int = 8, end: date | None = None) -> list[tuple[date, date]]:
    """Return (monday, sunday) pairs for the last num_weeks weeks ending at `end`."""
    if end is None:
        end = date.today()
    current_monday = monday_of(end)
    weeks = []
    for i in range(num_weeks):
        mon = current_monday - timedelta(weeks=i)
        sun = mon + timedelta(days=6)
        weeks.append((mon, sun))
    weeks.reverse()
    return weeks


def week_label(monday: date, range_format: bool = False, day_first: bool = False) -> str:
    """Human-readable week label.

    range_format=False, day_first=False: 'Jan 6'
    range_format=True:                   'Jan 6 – Jan 12'
    day_first=True:                      '6-Jan'
    """
    if range_format:
        sunday = monday + timedelta(days=6)
        return f"{monday.strftime('%b %-d')} – {sunday.strftime('%b %-d')}"
    if day_first:
        return f"{monday.day}-{monday.strftime('%b')}"
    return monday.strftime("%b %-d")


def resolve_quarter(labels: Sequence[str], quarter_config: list[dict]) -> str | None:
    """Given an issue's labels, return the quarter name from config mapping."""
    label_set = set(labels)
    for q in quarter_config:
        if q["label"] in label_set:
            return q["name"]
    return None


def parse_date(value: str | None) -> datetime | None:
    """Parse ISO datetime string from Jira fields."""
    if not value:
        return None
    try:
        clean = value.replace("Z", "+00:00")
        if "T" in clean:
            # Strip timezone offset for naive datetime
            if "+" in clean[10:]:
                clean = clean[:clean.rfind("+")]
            elif "-" in clean[11:]:
                last_dash = clean.rfind("-")
                if last_dash > 10:
                    clean = clean[:last_dash]
            return datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S.%f") if "." in clean else datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S")
        return datetime.strptime(clean, "%Y-%m-%d")
    except ValueError:
        return None


def days_between(start: str | datetime | None, end: str | datetime | None) -> float | None:
    """Calculate days between two dates. Accepts strings or datetimes."""
    if isinstance(start, str):
        start = parse_date(start)
    if isinstance(end, str):
        end = parse_date(end)
    if not start or not end:
        return None
    delta = end - start
    return delta.total_seconds() / 86400
