"""Review scheduling uses market close times; completions remain immutable events."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC8 = timezone(timedelta(hours=8))


def legacy_review_due_at(entry: dict) -> str | None:
    explicit = entry.get("review_after")
    if explicit:
        stamp = datetime.fromisoformat(explicit)
        if stamp.tzinfo is None:
            raise ValueError("复盘成熟时间必须包含时区")
        return stamp.astimezone(UTC8).isoformat()
    day = entry.get("review_at")
    if not day:
        return None
    # Registry dates are US session labels, not Beijing calendar dates. Using
    # 16:00 ET is conservative on early closes and follows DST automatically.
    close = datetime.combine(date.fromisoformat(day), time(16), ZoneInfo("America/New_York"))
    return close.astimezone(UTC8).isoformat()


def is_review_due(value: str, clock: datetime) -> bool:
    if len(value) == 10:
        return date.fromisoformat(value) <= clock.astimezone(UTC8).date()
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("复盘时间必须包含时区")
    return stamp <= clock
