"""Shippo tracking test fixtures."""

import pytest

from shippo_tracking.exceptions import ShippoClientError, ShippoTrackingDetailNotFoundError
from shippo_tracking.models import (
    ShippoTrackingDetail,
    ShippoTrackingEvent,
    ShippoTrackingResponse,
    ShippoTrackingStatus,
)


class FakeShippoRepo:
    """In-memory fake for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, ShippoTrackingDetail] = {}

    def get_tracking_detail(self, tracking_number: str) -> ShippoTrackingDetail:
        if tracking_number not in self._store:
            raise ShippoTrackingDetailNotFoundError(f"Not found: {tracking_number}")
        return self._store[tracking_number]

    def list_tracking_details(self) -> list[ShippoTrackingDetail]:
        return list(self._store.values())

    def save_tracking_detail(self, detail: ShippoTrackingDetail) -> None:
        self._store[detail.tracking_number] = detail

    def delete_tracking_detail(self, tracking_number: str) -> None:
        if tracking_number not in self._store:
            raise ShippoTrackingDetailNotFoundError(f"Not found: {tracking_number}")
        del self._store[tracking_number]


class FakeShippoClient:
    """Fake Shippo API client for unit tests."""

    def __init__(self, responses: dict[str, ShippoTrackingResponse] | None = None):
        self._responses = responses or {}

    def add_response(self, carrier: str, tracking_number: str, response: ShippoTrackingResponse):
        """Register a canned response for a carrier/tracking_number pair."""
        self._responses[f"{carrier}/{tracking_number}"] = response

    def get_tracking_status(self, carrier: str, tracking_number: str) -> ShippoTrackingResponse:
        key = f"{carrier}/{tracking_number}"
        if key not in self._responses:
            raise ShippoClientError(f"No response configured for {key}")
        return self._responses[key]

    def register_tracking(self, carrier: str, tracking_number: str) -> ShippoTrackingResponse:
        key = f"{carrier}/{tracking_number}"
        if key not in self._responses:
            raise ShippoClientError(f"No response configured for {key}")
        return self._responses[key]


@pytest.fixture()
def fake_repo():
    """Provide a fresh FakeShippoRepo for each test."""
    return FakeShippoRepo()


@pytest.fixture()
def fake_client():
    """Provide a fresh FakeShippoClient for each test."""
    return FakeShippoClient()


@pytest.fixture()
def sample_tracking_response() -> ShippoTrackingResponse:
    """A representative Shippo tracking API response."""
    return ShippoTrackingResponse(
        carrier="usps",
        tracking_number="9400111899223456789012",
        tracking_status=ShippoTrackingStatus(
            status="TRANSIT",
            substatus={"code": "package_arrived"},
            status_details="Package arrived at post office.",
            status_date="2026-03-19T14:30:00Z",
        ),
        tracking_history=[
            ShippoTrackingEvent(
                status="PRE_TRANSIT",
                substatus={"code": "information_received"},
                status_details="Shipping label created.",
                status_date="2026-03-17T08:00:00Z",
            ),
            ShippoTrackingEvent(
                status="TRANSIT",
                substatus={"code": "package_accepted"},
                status_details="Package accepted by carrier.",
                status_date="2026-03-18T10:15:00Z",
            ),
        ],
        eta="2026-03-21T18:00:00Z",
    )


@pytest.fixture()
def delivered_tracking_response() -> ShippoTrackingResponse:
    """A Shippo tracking response with DELIVERED status."""
    return ShippoTrackingResponse(
        carrier="usps",
        tracking_number="9400111899223456789012",
        tracking_status=ShippoTrackingStatus(
            status="DELIVERED",
            substatus={"code": "other"},
            status_details="Delivered to front door.",
            status_date="2026-03-20T12:00:00Z",
        ),
        tracking_history=[
            ShippoTrackingEvent(
                status="TRANSIT",
                substatus={"code": "out_for_delivery"},
                status_details="Out for delivery.",
                status_date="2026-03-20T07:00:00Z",
            ),
            ShippoTrackingEvent(
                status="DELIVERED",
                substatus={"code": "other"},
                status_details="Delivered to front door.",
                status_date="2026-03-20T12:00:00Z",
            ),
        ],
    )
