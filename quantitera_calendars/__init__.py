"""Finite cash calendars; historical additions keep prospective timing unchanged."""
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

# Frozen prospective records use this version for 2025/2026 entry/exit times.
VERSION = "cash-calendar-2025-2026-v1"
HISTORY_VERSION = "cash-history-calendar-2021-2026-v1"
YEARS = {2021, 2022, 2023, 2024, 2025, 2026}
ZONES = {"US": "America/New_York", "HK": "Asia/Hong_Kong", "CN": "Asia/Shanghai"}
SOURCE_REFS = {
    "US": ["https://www.nyse.com/trade/hours-calendars",
           "https://www.nyse.com/publicdocs/ICE_NYSE_2025_Yearly_Trading_Calendar.pdf",
           "https://ir.theice.com/press/news-details/2024/The-New-York-Stock-Exchange-Will-Close-Markets-on-January-9-to-Honor-the-Passing-of-Former-President-Jimmy-Carter-on-National-Day-of-Mourning/default.aspx"],
    "HK": ["https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/SEHK/2024/ce_SEHK_CT_063_2024.pdf",
           "https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/SEHK/2025/ce_SEHK_CT_075_2025.pdf",
           "https://www.hkex.com.hk/Services/Trading/Securities/Overview/Trading-Mechanism?sc_lang=en"],
    "CN": ["https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20241223_10767110.shtml",
           "https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml"],
}


def _days(text):
    return {date.fromisoformat(x) for x in text.split()}


HOLIDAYS = {
    "US": _days("2025-01-01 2025-01-09 2025-01-20 2025-02-17 2025-04-18 2025-05-26 "
                "2025-06-19 2025-07-04 2025-09-01 2025-11-27 2025-12-25 "
                "2026-01-01 2026-01-19 2026-02-16 2026-04-03 2026-05-25 2026-06-19 "
                "2026-07-03 2026-09-07 2026-11-26 2026-12-25"),
    "HK": _days("2025-01-01 2025-01-29 2025-01-30 2025-01-31 2025-04-04 2025-04-18 "
                "2025-04-21 2025-05-01 2025-05-05 2025-07-01 2025-10-01 2025-10-07 "
                "2025-10-29 2025-12-25 2025-12-26 2026-01-01 2026-02-17 2026-02-18 "
                "2026-02-19 2026-04-03 2026-04-06 2026-04-07 2026-05-01 2026-05-25 "
                "2026-06-19 2026-07-01 2026-10-01 2026-10-19 2026-12-25"),
    "CN": set(),
}
for start, end in (
    ("2025-01-01", "2025-01-01"), ("2025-01-28", "2025-02-04"),
    ("2025-04-04", "2025-04-06"), ("2025-05-01", "2025-05-05"),
    ("2025-05-31", "2025-06-02"), ("2025-10-01", "2025-10-08"),
    ("2026-01-01", "2026-01-03"), ("2026-02-15", "2026-02-23"),
    ("2026-04-04", "2026-04-06"), ("2026-05-01", "2026-05-05"),
    ("2026-06-19", "2026-06-21"), ("2026-09-25", "2026-09-27"),
    ("2026-10-01", "2026-10-07"),
):
    day = date.fromisoformat(start)
    while day <= date.fromisoformat(end):
        HOLIDAYS["CN"].add(day)
        day += timedelta(days=1)
HALF_DAYS = {
    "US": _days("2025-07-03 2025-11-28 2025-12-24 2026-11-27 2026-12-24"),
    "HK": _days("2025-01-28 2025-12-24 2025-12-31 2026-02-16 2026-12-24 2026-12-31"),
    "CN": set(),
}

_historical_raw = Path(__file__).with_name("cash_history_2021_2024.json").read_bytes()
_historical = json.loads(_historical_raw)
if _historical["version"] != "cash-history-2021-2024-v1" or _historical["years"] != [2021, 2022, 2023, 2024]:
    raise ValueError("historical calendar identity mismatch")
HISTORY_SHA256 = hashlib.sha256(_historical_raw).hexdigest()
SPECIAL_TIMES = {}
for _venue, _market in _historical["markets"].items():
    HOLIDAYS[_venue].update(_days(" ".join(_market["holidays"])))
    HALF_DAYS[_venue].update(_days(" ".join(_market["half_days"])))
    SPECIAL_TIMES[_venue] = _market["special_times"]
    SOURCE_REFS[_venue] += _historical["source_refs"][_venue]


def aware(clock):
    if not isinstance(clock, datetime) or clock.utcoffset() is None:
        raise ValueError("研究时间须包含时区")
    return clock


def check(venue, day):
    if venue not in ZONES or day.year not in YEARS:
        raise ValueError(f"unsupported_calendar: {venue}/{day.year}; registered 2021—2026 only")


def is_session(venue, day):
    check(venue, day)
    return day.weekday() < 5 and day not in HOLIDAYS[venue]


def session_times(venue, day):
    if not is_session(venue, day):
        raise ValueError(f"非交易日: {venue}/{day}")
    zone = ZoneInfo(ZONES[venue])
    special = SPECIAL_TIMES[venue].get(day.isoformat())
    if special:
        return tuple(datetime.combine(day, time.fromisoformat(special[k]), zone) for k in ("open", "close"))
    # HK bound includes the random closing auction (up to 16:10/12:10).
    hour, minute = {"US": (13 if day in HALF_DAYS[venue] else 16, 0),
                    "HK": (12 if day in HALF_DAYS[venue] else 16, 10), "CN": (15, 0)}[venue]
    return datetime.combine(day, time(9, 30), zone), datetime.combine(day, time(hour, minute), zone)


def available_at(venue, day):
    return session_times(venue, day)[1] + timedelta(minutes=15)


def sessions(venue, start, end):
    if start > end:
        return []
    check(venue, start)
    check(venue, end)
    output = []
    day = start
    while day <= end:
        if is_session(venue, day):
            output.append(day)
        day += timedelta(days=1)
    return output


def latest_completed(venue, clock):
    aware(clock)
    if venue not in ZONES:
        raise ValueError("unsupported_calendar")
    day = clock.astimezone(ZoneInfo(ZONES[venue])).date()
    check(venue, day)
    for _ in range(25):
        if is_session(venue, day) and available_at(venue, day) <= clock:
            return day
        day -= timedelta(days=1)
    raise ValueError("没有已完成且日历支持的交易日")


def completed_week_cutoff(clock):
    """Friday 23:59 UTC: all three markets have closed, including US DST."""
    day = aware(clock).astimezone(timezone.utc).date()
    friday = day - timedelta(days=(day.weekday() - 4) % 7)
    cutoff = datetime.combine(friday, time(23, 59), timezone.utc)
    if cutoff > clock:
        cutoff -= timedelta(days=7)
    return cutoff
