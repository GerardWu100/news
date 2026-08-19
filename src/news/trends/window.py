"""Turn an explicit start and end date into a Google Trends time window.

Google's library also accepts today-anchored shorthands such as ``today 3-m``
and ``now 7-d``. This project never uses them: they resolve against the day the
request runs, so the same code returns a different window tomorrow and no
result reproduces. This module is the only place a timeframe string is built,
and it can only be built from two explicit dates.

The window length also decides the spacing of the points Google returns, which
is not a setting. Roughly: up to 7 days gives hourly, up to 9 months gives
daily, up to 5 years gives weekly, and longer gives monthly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from news.trends.models import TrendsValidationError

# Google's archive begins in 2004; earlier dates return nothing useful.
EARLIEST_SUPPORTED_DATE = date(2004, 1, 1)
# Beyond roughly this many days Google downgrades daily points to weekly ones.
MAX_DAYS_FOR_DAILY_POINTS = 269
ISO_DATE_LENGTH = 10


@dataclass(frozen=True, slots=True)
class TrendsWindow:
    """One inclusive historical window, already validated.

    Attributes
    ----------
    start_date : date
        Inclusive first day of the window.
    end_date : date
        Inclusive last day of the window.
    """

    start_date: date
    end_date: date

    @property
    def length_in_days(self) -> int:
        """Return the inclusive number of days the window covers."""
        return (self.end_date - self.start_date).days + 1

    @property
    def returns_daily_points(self) -> bool:
        """Report whether Google will return daily rather than weekly points."""
        return self.length_in_days <= MAX_DAYS_FOR_DAILY_POINTS

    def to_timeframe(self) -> str:
        """Render the window in the ``YYYY-MM-DD YYYY-MM-DD`` form Google wants."""
        return f"{self.start_date.isoformat()} {self.end_date.isoformat()}"


def build_trends_window(
    start_date: str,
    end_date: str,
    *,
    today: date | None = None,
) -> TrendsWindow:
    """Validate two ISO dates and return the window they describe.

    Parameters
    ----------
    start_date : str
        Inclusive window start in ``YYYY-MM-DD`` format.
    end_date : str
        Inclusive window end in ``YYYY-MM-DD`` format.
    today : date | None, optional
        Current calendar date used to reject future windows. Tests may inject a
        fixed date; production uses the machine's local date.

    Returns
    -------
    TrendsWindow
        Validated window ready to be converted to a timeframe string.

    Raises
    ------
    TrendsValidationError
        If either date is malformed, the order is reversed, or the start
        predates Google's archive.
    """
    parsed_start = parse_iso_date(start_date, field_name="start_date")
    parsed_end = parse_iso_date(end_date, field_name="end_date")

    if parsed_start > parsed_end:
        raise TrendsValidationError("start_date must be on or before end_date.")
    if parsed_start < EARLIEST_SUPPORTED_DATE:
        raise TrendsValidationError(
            "Google Trends history begins on "
            f"{EARLIEST_SUPPORTED_DATE.isoformat()}; choose a later start_date."
        )
    current_date = today or date.today()
    if parsed_end > current_date:
        raise TrendsValidationError(
            f"end_date cannot be after today ({current_date.isoformat()})."
        )

    return TrendsWindow(start_date=parsed_start, end_date=parsed_end)


def parse_iso_date(raw_value: str, *, field_name: str) -> date:
    """Parse one ``YYYY-MM-DD`` string into a date.

    Parameters
    ----------
    raw_value : str
        Candidate date string.
    field_name : str
        Name used in the error message so the caller knows which input failed.

    Returns
    -------
    date
        The parsed calendar date.

    Raises
    ------
    TrendsValidationError
        If the value is not exactly one ISO calendar date.
    """
    cleaned = raw_value.strip()
    # Reject anything that is not exactly a calendar date, which also rejects
    # Google's today-anchored shorthands such as "today 3-m".
    if len(cleaned) != ISO_DATE_LENGTH:
        raise TrendsValidationError(
            f"Invalid {field_name}: expected an exact date as YYYY-MM-DD."
        )
    try:
        return date.fromisoformat(cleaned)
    except ValueError as exc:
        raise TrendsValidationError(
            f"Invalid {field_name}: expected an exact date as YYYY-MM-DD."
        ) from exc
