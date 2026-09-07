import pytz

from datetime import date, datetime, time

def convert_timezone_date(
    source_date: date,
    source_timezone: str,
    target_timezone: str = "Asia/Bangkok",
) -> date:
    """
    Convert a date at 08:30 from one timezone to another.

    Args:
        source_date: Date to convert.
        source_timezone: Source timezone name, such as "America/New_York".
        target_timezone: Destination timezone name. Defaults to "Asia/Bangkok".

    Returns:
        The corresponding date in the destination timezone.
    """
    reference_time = time(hour=8, minute=30)

    source_tz = pytz.timezone(source_timezone)
    target_tz = pytz.timezone(target_timezone)

    source_datetime = source_tz.localize(
        datetime.combine(source_date, reference_time)
    )
    target_datetime = source_datetime.astimezone(target_tz)

    return target_datetime.date()