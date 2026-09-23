"""pipeline.py + wiki.py helpers: periods, months, run naming."""
import datetime as dt

import pytest

from wiki_interest import pipeline, wiki


def test_month_helpers():
    assert wiki.add_months(dt.date(2024, 11, 1), 3) == dt.date(2025, 2, 1)
    assert wiki.month_range(dt.date(2024, 11, 1), dt.date(2025, 1, 1)) == ["2024-11", "2024-12", "2025-01"]
    assert wiki._range_params(dt.date(2024, 2, 1), dt.date(2024, 2, 1)) == ("2024020100", "2024022900")


def test_period_never_includes_current_month_or_pre_2015():
    start, end = pipeline.period(24, end="2999-01")
    assert end == wiki.last_full_month()
    assert pipeline.period(24, start="2010-01", end="2016-01")[0] == pipeline.PAGEVIEWS_START


def test_parse_articles():
    assert pipeline.parse_articles(["pl:Post", "sk: Pôst ", "pl:Głodówka"]) == \
        {"pl": ["Post", "Głodówka"], "sk": ["Pôst"]}


def test_run_name_depends_on_languages():
    a, b = dt.date(2024, 1, 1), dt.date(2025, 12, 1)
    name = pipeline.run_name
    assert name(["X"], ["pl", "cs"], a, b) == name(["X"], ["cs", "pl"], a, b)
    assert name(["X"], ["pl", "cs"], a, b) != name(["X"], ["pl", "cs", "sk"], a, b)
    assert name(["X"], ["pl"], a, b) != name(["X"], ["pl"], a, b, redirects=True)
    assert len(name(["X"], wiki.TOP_LANGS, a, b)) < 60


def test_bad_month_gives_clear_error():
    with pytest.raises(ValueError, match="YYYY-MM"):
        wiki.parse_month("bad")


def test_start_after_end_gives_clear_error():
    with pytest.raises(ValueError, match="before"):
        pipeline.period(24, start="2026-05", end="2025-01")
