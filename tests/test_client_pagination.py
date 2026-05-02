"""Tests for activity-list pagination filtering (issue #23)."""

from garmin_client.client import _activities_in_range


def _act(activity_id: int, start_local: str) -> dict:
    return {"activityId": activity_id, "startTimeLocal": start_local}


class TestActivitiesInRange:
    """Issue #23: Garmin's activitylist endpoint ignores startDate/endDate
    query params and returns all activities. We filter client-side and
    rely on the reverse-chronological ordering to break the pagination
    loop early (saw_older=True) once the page has dipped past the start
    of the requested window.
    """

    def test_all_activities_within_range(self):
        page = [
            _act(1, "2026-04-09T10:00:00"),
            _act(2, "2026-04-09T08:00:00"),
            _act(3, "2026-04-08T19:00:00"),
        ]
        in_range, saw_older = _activities_in_range(page, "2026-04-08", "2026-04-09")
        assert [a["activityId"] for a in in_range] == [1, 2, 3]
        assert saw_older is False

    def test_newest_first_with_older_at_end_signals_break(self):
        # Realistic --latest scenario: Garmin returns 100 newest activities
        # back-to-back; only the first matches the 1-day window.
        page = [
            _act(1, "2026-04-09T10:00:00"),  # in range
            _act(2, "2026-04-08T20:00:00"),  # older — signals break
            _act(3, "2026-04-08T18:00:00"),  # older
        ]
        in_range, saw_older = _activities_in_range(page, "2026-04-09", "2026-04-09")
        assert [a["activityId"] for a in in_range] == [1]
        assert saw_older is True

    def test_all_older_returns_empty_and_signals_break(self):
        page = [
            _act(1, "2025-12-01T10:00:00"),
            _act(2, "2025-11-15T10:00:00"),
        ]
        in_range, saw_older = _activities_in_range(page, "2026-04-09", "2026-04-09")
        assert in_range == []
        assert saw_older is True

    def test_activity_after_end_date_is_dropped_without_break(self):
        # Activity newer than e_date — out of range but doesn't trigger
        # the break (we may still find in-range activities further down).
        page = [
            _act(1, "2026-05-15T10:00:00"),  # too new — drop, don't break
            _act(2, "2026-04-09T08:00:00"),  # in range
        ]
        in_range, saw_older = _activities_in_range(page, "2026-04-09", "2026-04-09")
        assert [a["activityId"] for a in in_range] == [2]
        assert saw_older is False

    def test_missing_start_time_is_kept_defensively(self):
        page = [
            _act(1, "2026-04-09T10:00:00"),
            {"activityId": 2},  # no startTimeLocal at all
            {"activityId": 3, "startTimeLocal": None},
            {"activityId": 4, "startTimeLocal": ""},
        ]
        in_range, saw_older = _activities_in_range(page, "2026-04-09", "2026-04-09")
        # All four kept — better to over-include than silently drop
        assert [a["activityId"] for a in in_range] == [1, 2, 3, 4]
        assert saw_older is False

    def test_non_dict_entries_are_skipped(self):
        page = [_act(1, "2026-04-09T10:00:00"), None, "garbage", 42]
        in_range, saw_older = _activities_in_range(page, "2026-04-09", "2026-04-09")
        assert len(in_range) == 1
        assert in_range[0]["activityId"] == 1
        assert saw_older is False

    def test_empty_page(self):
        in_range, saw_older = _activities_in_range([], "2026-04-09", "2026-04-09")
        assert in_range == []
        assert saw_older is False
