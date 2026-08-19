"""Rescale a fetched series so it only reflects what was known at a date.

The problem this solves
-----------------------

Google divides every value in a response by the highest value anywhere in the
requested window. Writing ``v_t`` for the true search volume on day ``t`` and
``[s, e]`` for the requested window, what comes back is::

    I_t = round(100 * v_t / max(v_u for u in [s, e]))

The divisor looks at the whole window, including days after ``t``. So a series
fetched for all of 2017 tells every January value where the May peak sat. A
study standing on 2017-01-05 that reads such a value is using information from
five months later, which is look-ahead bias arriving through the scaling rather
than through the choice of data.

Measured example, same keyword and geography, only the end date differs::

    date         window Jan-Mar    window Jan-Sep    ratio
    2017-01-05   100                30               3.33
    2017-01-06    86                26               3.31

The ratio is the same on every day, because the leak is one shared divisor.

What this module does
---------------------

:func:`rebase_as_of` drops every point after a chosen decision date and divides
what remains by the largest value up to that date::

    rebased_t = 100 * I_t / max(I_u for u <= decision_date)

The result is the scale a researcher standing on the decision date could have
seen. It costs one local calculation instead of one network request per
decision date.

Two properties worth knowing:

- **One divisor for all keywords.** Google puts every keyword in a request on
  one shared scale, so comparing them is meaningful. The rebasing keeps that by
  dividing all keywords by a single number, the maximum across all of them.
  Rescaling each keyword separately would silently destroy the comparison.
- **It cannot restore lost precision.** Google returns whole numbers. If the
  original window contained a much later spike, early values already arrived
  rounded to single digits, and no rescaling brings back the detail that
  rounding removed. Fetching a window that ends near the decision date is still
  the more accurate route; this is the cheap approximation.
"""

from __future__ import annotations

from news.trends.models import (
    GRANULARITY_DAILY,
    GRANULARITY_HOURLY,
    InterestOverTime,
    TrendsValidationError,
)
from news.trends.window import parse_iso_date

# Google's index tops out at 100, and the rebased series uses the same top.
INDEX_MAXIMUM = 100.0
# Decimal places kept in the rebased values. Google's own values are whole
# numbers; two places is enough to keep the ratios between them visible.
REBASED_DECIMAL_PLACES = 2


def rebase_as_of(series: InterestOverTime, decision_date: str) -> InterestOverTime:
    """Rescale a series to the information available on one date.

    Parameters
    ----------
    series : InterestOverTime
        A fetched series, normally still on Google's original scale.
    decision_date : str
        The date the study stands on, in ``YYYY-MM-DD`` format. Must fall
        inside the series window. Points after it are dropped; the remaining
        points are divided by the largest value up to it.

    Returns
    -------
    InterestOverTime
        A new series ending on ``decision_date``, with ``anchor_date`` set to
        that date and ``end_date`` moved back to match. The original is not
        modified.

    Raises
    ------
    TrendsValidationError
        If the date is malformed, falls outside the window, or leaves no
        points.

    Examples
    --------
    A series whose peak sits after the decision date is rescaled to the peak
    that had already happened::

        dates   2017-01-01  2017-01-02  2017-01-03
        before          14          24          30
        after           46.67       80.0       100.0

    Before rebasing, 30 was measured against a later peak of 100. After, the
    largest value up to the decision date becomes 100 and the earlier days keep
    their ratios: 14/30 and 24/30 of it.
    """
    parsed_decision_date = parse_iso_date(decision_date, field_name="decision_date")
    normalized_decision_date = parsed_decision_date.isoformat()

    window_start = parse_iso_date(series.start_date, field_name="start_date")
    window_end = parse_iso_date(series.end_date, field_name="end_date")
    if not window_start <= parsed_decision_date <= window_end:
        raise TrendsValidationError(
            f"decision_date {normalized_decision_date} is outside the series "
            f"window {series.start_date} to {series.end_date}."
        )

    safe_local_granularities = {GRANULARITY_HOURLY, GRANULARITY_DAILY}
    if (
        parsed_decision_date < window_end
        and series.granularity not in safe_local_granularities
    ):
        raise TrendsValidationError(
            "Local as-of rescaling requires hourly or daily points. Weekly, "
            "monthly, and unknown-granularity points can include observations "
            "after the decision date; fetch a window ending on that date instead."
        )

    kept_count = _count_points_up_to(series.dates, normalized_decision_date)
    if kept_count == 0:
        raise TrendsValidationError(
            f"The series has no points on or before {normalized_decision_date}."
        )

    kept_values = {
        keyword: points[:kept_count] for keyword, points in series.values.items()
    }
    # One divisor across every keyword, so the keywords stay comparable with
    # each other exactly as Google returned them.
    highest_known_value = max(
        (value for points in kept_values.values() for value in points),
        default=0.0,
    )

    if highest_known_value > 0:
        rebased_values = {
            keyword: tuple(
                round(
                    INDEX_MAXIMUM * value / highest_known_value,
                    REBASED_DECIMAL_PLACES,
                )
                for value in points
            )
            for keyword, points in kept_values.items()
        }
    else:
        # Every known value is zero, usually low-volume censoring rather than
        # true absence. There is nothing to scale against, so the zeros are
        # kept as they are.
        rebased_values = kept_values

    return InterestOverTime(
        keywords=series.keywords,
        start_date=series.start_date,
        end_date=normalized_decision_date,
        geo=series.geo,
        granularity=series.granularity,
        dates=series.dates[:kept_count],
        is_partial=series.is_partial[:kept_count],
        values=rebased_values,
        anchor_date=normalized_decision_date,
        fetched_at=series.fetched_at,
    )


def _count_points_up_to(dates: tuple[str, ...], decision_date: str) -> int:
    """Count leading points dated on or before the decision date.

    Labels are ``YYYY-MM-DD`` or ``YYYY-MM-DD HH:MM`` and arrive oldest first,
    so comparing the first ten characters as text orders them correctly and
    handles hourly data without extra parsing.
    """
    kept = 0
    for label in dates:
        if label[:10] > decision_date:
            break
        kept += 1
    return kept
