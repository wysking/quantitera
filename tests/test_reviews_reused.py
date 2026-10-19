from datetime import datetime
import pytest
from research_engine.reviews import is_review_due, legacy_review_due_at


@pytest.mark.parametrize("session,expected", [
    ("2026-10-01", "2026-10-02T04:00:00+08:00"),
    ("2026-11-02", "2026-11-03T05:00:00+08:00"),
])
def test_us_review_matures_after_close_with_dst(session, expected):
    assert legacy_review_due_at({"review_at": session}) == expected
    assert not is_review_due(expected, datetime.fromisoformat(expected.replace("04:00", "03:59").replace("05:00", "04:59")))
    assert is_review_due(expected, datetime.fromisoformat(expected))
