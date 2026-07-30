"""Fiscal year calendar — auto-resolves current quarter from date."""

from __future__ import annotations

from datetime import date


def current_quarter_label(
    today: date | None = None,
    fy_start_month: int = 5,
    pattern: str = "ATDT_FY{fy}Q{q}",
) -> str:
    """Compute the current quarter label from a date.

    Arctic Wolf fiscal year starts in May (month 5).
    FY27 = May 2026 – Apr 2027.
    Q1 = May–Jul, Q2 = Aug–Oct, Q3 = Nov–Jan, Q4 = Feb–Apr.
    """
    if today is None:
        today = date.today()

    month = today.month
    year = today.year

    months_into_fy = (month - fy_start_month) % 12
    quarter = months_into_fy // 3 + 1

    if month >= fy_start_month:
        fy = year - 2000 + 1
    else:
        fy = year - 2000

    return pattern.format(fy=fy, q=quarter)


def quarter_boundaries(
    label: str,
    fy_start_month: int = 5,
    pattern: str = "ATDT_FY{fy}Q{q}",
) -> tuple[date, date]:
    """Return (start_date, end_date) for a given quarter label."""
    prefix = pattern.split("{fy}")[0]
    rest = label[len(prefix):]
    fy = int(rest.split("Q")[0])
    q = int(rest.split("Q")[1])

    cal_year = 2000 + fy - 1 if fy_start_month <= 12 else 2000 + fy
    start_month = fy_start_month + (q - 1) * 3

    if start_month > 12:
        start_month -= 12
        cal_year += 1

    start = date(cal_year, start_month, 1)

    end_month = start_month + 3
    end_year = cal_year
    if end_month > 12:
        end_month -= 12
        end_year += 1
    from datetime import timedelta
    end = date(end_year, end_month, 1) - timedelta(days=1)

    return start, end


def all_quarter_labels(
    num_quarters: int = 3,
    today: date | None = None,
    fy_start_month: int = 5,
    pattern: str = "ATDT_FY{fy}Q{q}",
) -> list[str]:
    """Return labels for the last N quarters (current first)."""
    if today is None:
        today = date.today()

    labels = []
    for offset in range(num_quarters):
        month = today.month - offset * 3
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        shifted = date(year, month, 1)
        labels.append(current_quarter_label(shifted, fy_start_month, pattern))

    return labels
