"""Turn a news search query into Google Trends keywords.

The news search accepts a free-form query string that providers interpret as a
boolean expression, for example::

    "central bank" AND (inflation OR rates) -crypto

Google Trends accepts no operators at all. It takes at most five plain search
terms and puts them on one shared scale. This module is the bridge between the
two, so the browser and the command line can send the same query they already
typed for articles and get a matching attention series.

What it does to a query:

- A double-quoted run becomes one keyword, spaces included, quotes removed.
- Bare words become individual keywords.
- The operators ``AND``, ``OR``, ``NOT`` are dropped, in any capitalization.
- A term marked for exclusion (``-crypto`` or ``NOT crypto``) is dropped,
  because Trends cannot express exclusion and keeping it would measure the
  opposite of what the query asked for.
- Parentheses and a leading ``+`` are stripped.
- Repeats are removed, ignoring capitalization, keeping the first spelling.

Worked example. Input::

    "central bank" AND (inflation OR Inflation) -crypto

Tokens found, in order: ``central bank``, ``AND``, ``inflation``,
``OR``, ``Inflation``, ``-crypto``. After dropping operators, dropping the
excluded term, and removing the repeat, the result is::

    ("central bank", "inflation")
"""

from __future__ import annotations

import re

from news.trends.models import TrendsValidationError

# Google Trends puts at most five terms on one shared 0-100 scale.
MAX_KEYWORDS = 5
# Words that join terms in a provider query and carry no search meaning.
BOOLEAN_OPERATORS = frozenset({"and", "or", "not"})
# Characters that structure a boolean query but are not part of any term.
STRUCTURAL_CHARACTERS = "()"
# One quoted phrase, or one run of non-space characters.
TOKEN_PATTERN = re.compile(r'"([^"]*)"|(\S+)')


def keywords_from_query(query: str, *, max_keywords: int = MAX_KEYWORDS) -> tuple[str, ...]:
    """Extract plain Trends keywords from a news search query.

    Parameters
    ----------
    query : str
        The same query string the news search receives.
    max_keywords : int, optional
        Upper bound on returned keywords. Defaults to Google's limit of five.
        Extra terms are dropped from the end rather than causing an error, so
        a long article query still produces a usable series.

    Returns
    -------
    tuple[str, ...]
        Ordered keywords, at most ``max_keywords`` of them.

    Raises
    ------
    TrendsValidationError
        If the query contains no usable term, for example when it is blank or
        holds only operators and exclusions.
    """
    if max_keywords < 1:
        raise TrendsValidationError("max_keywords must be at least 1.")

    keywords: list[str] = []
    already_seen: set[str] = set()
    # A NOT applies to the term after it, so exclusion is carried one token
    # forward. Any other token clears the flag.
    next_term_is_excluded = False

    for match in TOKEN_PATTERN.finditer(query):
        quoted_phrase, bare_word = match.group(1), match.group(2)

        if quoted_phrase is not None:
            candidate = quoted_phrase.strip()
            is_excluded = next_term_is_excluded
            next_term_is_excluded = False
        else:
            word = bare_word.strip(STRUCTURAL_CHARACTERS)
            if word.lower() in BOOLEAN_OPERATORS:
                # "NOT" marks the following term; "AND"/"OR" only join terms.
                next_term_is_excluded = word.lower() == "not"
                continue
            is_excluded = next_term_is_excluded or word.startswith("-")
            next_term_is_excluded = False
            candidate = word.lstrip("+-").strip()

        if is_excluded or not candidate:
            continue

        comparison_key = candidate.lower()
        if comparison_key in already_seen:
            continue
        already_seen.add(comparison_key)
        keywords.append(candidate)

        if len(keywords) == max_keywords:
            break

    if not keywords:
        raise TrendsValidationError(
            "The query contains no keyword Google Trends can search. "
            "Provide at least one term that is not an operator or an exclusion."
        )
    return tuple(keywords)
