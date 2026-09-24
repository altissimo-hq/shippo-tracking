"""Unit tests for ShippoRepo query construction."""

import pytest

from altissimo.shippo_tracking.models import ShippoTrackingDetail
from altissimo.shippo_tracking.repo import ShippoRepo

pytestmark = pytest.mark.unit


@pytest.fixture
def find_calls(monkeypatch):
    calls: list[tuple] = []

    def fake_find(*args):
        calls.append(args)
        return []

    monkeypatch.setattr(ShippoTrackingDetail, "find", fake_find, raising=False)
    return calls


class TestListTrackingDetails:
    """Tests for ShippoRepo.list_tracking_details filters."""

    def test_no_filter(self, find_calls):
        ShippoRepo().list_tracking_details()
        assert find_calls == [()]

    def test_status_filter_uppercased(self, find_calls):
        ShippoRepo().list_tracking_details(status="delivered")
        assert find_calls == [({"status": "DELIVERED"},)]

    def test_exclude_status_filter(self, find_calls):
        ShippoRepo().list_tracking_details(exclude_status="delivered")
        assert find_calls == [({"status": {"!=": "DELIVERED"}},)]
