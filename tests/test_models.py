"""Unit tests for Shippo models."""

import pytest

from shippo_tracking.models import (
    ShippoLocation,
    ShippoTrackingDetail,
    ShippoTrackingEvent,
    ShippoTrackingResponse,
    ShippoTrackingStatusEnum,
    ShippoWebhookEvent,
)

pytestmark = pytest.mark.unit


class TestShippoTrackingStatusEnum:
    """Tests for ShippoTrackingStatusEnum."""

    def test_all_expected_values(self):
        values = {e.value for e in ShippoTrackingStatusEnum}
        assert "PRE_TRANSIT" in values
        assert "TRANSIT" in values
        assert "DELIVERED" in values
        assert "RETURNED" in values
        assert "FAILURE" in values
        assert "UNKNOWN" in values


class TestShippoLocation:
    """Tests for ShippoLocation model."""

    def test_minimal_construction(self):
        loc = ShippoLocation()
        assert loc.city is None
        assert loc.state is None

    def test_full_construction(self):
        loc = ShippoLocation(city="Boston", state="MA", zip="02101", country="US")
        assert loc.city == "Boston"
        assert loc.zip == "02101"

    def test_extra_fields_allowed(self):
        loc = ShippoLocation(city="Boston", extra_field="value")
        assert loc.city == "Boston"


class TestShippoTrackingEvent:
    """Tests for ShippoTrackingEvent model."""

    def test_construction(self):
        event = ShippoTrackingEvent(
            status="TRANSIT",
            substatus={"code": "package_accepted"},
            status_details="Accepted.",
            status_date="2026-03-18T10:00:00Z",
        )
        assert event.status == "TRANSIT"
        assert event.substatus.code == "package_accepted"


class TestShippoTrackingResponse:
    """Tests for ShippoTrackingResponse model."""

    def test_construction_with_history(self, sample_tracking_response):
        assert sample_tracking_response.carrier == "usps"
        assert sample_tracking_response.tracking_number == "9400111899223456789012"
        assert len(sample_tracking_response.tracking_history) == 2
        assert sample_tracking_response.tracking_status.status == "TRANSIT"

    def test_empty_history(self):
        resp = ShippoTrackingResponse(carrier="fedex", tracking_number="123")
        assert resp.tracking_history == []
        assert resp.tracking_status is None


class TestShippoWebhookEvent:
    """Tests for the webhook event model."""

    def test_construction(self):
        event = ShippoWebhookEvent(event="track_updated", data={"carrier": "usps"})
        assert event.event == "track_updated"
        assert event.data["carrier"] == "usps"

    def test_extra_fields_allowed(self):
        event = ShippoWebhookEvent(event="track_updated", data={}, extra="value")
        assert event.event == "track_updated"


class TestShippoTrackingDetail:
    """Tests for the persistence model."""

    def test_minimal_construction(self):
        detail = ShippoTrackingDetail(
            id="TRACK123",
            tracking_number="TRACK123",
            carrier="usps",
        )
        assert detail.tracking_number == "TRACK123"
        assert detail.carrier == "usps"
        assert detail.status is None
        assert detail.tracking_events == []
        assert detail.created_at is not None

    def test_update_from_response(self, sample_tracking_response):
        detail = ShippoTrackingDetail(
            id="9400111899223456789012",
            tracking_number="9400111899223456789012",
            carrier="usps",
        )
        detail.update_from_response(sample_tracking_response)

        assert detail.status == "TRANSIT"
        assert detail.substatus.code == "package_arrived"
        assert detail.eta == "2026-03-21T18:00:00Z"
        assert len(detail.tracking_events) == 2
        assert detail.updated_at is not None

    def test_update_preserves_tracking_number(self, sample_tracking_response):
        detail = ShippoTrackingDetail(
            id="9400111899223456789012",
            tracking_number="9400111899223456789012",
            carrier="usps",
            status="PRE_TRANSIT",
        )
        detail.update_from_response(sample_tracking_response)

        assert detail.tracking_number == "9400111899223456789012"
        assert detail.carrier == "usps"
        assert detail.status == "TRANSIT"
