from datetime import datetime
from zoneinfo import ZoneInfo

from .config import get_settings


def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def local(dt: datetime) -> datetime:
    return dt.astimezone(tz())


def fmt_time(dt: datetime) -> str:
    return local(dt).strftime("%H:%M")


def fmt_dt(dt: datetime) -> str:
    return local(dt).strftime("%d.%m.%Y %H:%M")
