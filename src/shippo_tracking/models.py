"""Shippo tracking models.

API response models mirror the Shippo REST API JSON shapes.
Persistence models (``ShippoTrackingDetail``) require the ``[firestore]`` extra.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ShippoTrackingStatusEnum(str, Enum):
    """Tracking status values returned by the Shippo API.

    See: https://docs.goshippo.com/docs/tracking/tracking/
    """

    PRE_TRANSIT = "PRE_TRANSIT"
    TRANSIT = "TRANSIT"
    DELIVERED = "DELIVERED"
    RETURNED = "RETURNED"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


class ShippoSubstatusEnum(str, Enum):
    """Substatus values for more granular tracking detail.

    See: https://docs.goshippo.com/docs/tracking/tracking/
    """

    INFORMATION_RECEIVED = "information_received"
    ADDRESS_ISSUE = "address_issue"
    CONTACT_CARRIER = "contact_carrier"
    DELAYED = "delayed"
    DELIVERY_ATTEMPTED = "delivery_attempted"
    DELIVERY_RESCHEDULED = "delivery_rescheduled"
    DELIVERY_SCHEDULED = "delivery_scheduled"
    LOCATION_INACCESSIBLE = "location_inaccessible"
    NOTICE_LEFT = "notice_left"
    OUT_FOR_DELIVERY = "out_for_delivery"
    PACKAGE_ACCEPTED = "package_accepted"
    PACKAGE_ARRIVED = "package_arrived"
    PACKAGE_DAMAGED = "package_damaged"
    PACKAGE_DEPARTED = "package_departed"
    PACKAGE_DISPOSED = "package_disposed"
    PACKAGE_FORWARDED = "package_forwarded"
    PACKAGE_HELD = "package_held"
    PACKAGE_LOST = "package_lost"
    PACKAGE_UNDELIVERABLE = "package_undeliverable"
    PICKUP_AVAILABLE = "pickup_available"
    RESCHEDULE_DELIVERY = "reschedule_delivery"
    RETURN_TO_SENDER = "return_to_sender"
    OTHER = "other"


# ---------------------------------------------------------------------------
# API response models — mirror the Shippo REST API JSON shapes
# ---------------------------------------------------------------------------


class ShippoLocation(BaseModel):
    """Location information from a tracking event."""

    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ShippoSubstatus(BaseModel):
    """Substatus object from the tracking API."""

    code: Optional[str] = None
    text: Optional[str] = None
    action_required: Optional[bool] = None

    model_config = ConfigDict(extra="allow")


class ShippoTrackingEvent(BaseModel):
    """A single tracking event in the tracking history.

    Maps to entries in the ``tracking_history`` array returned by the
    Shippo tracking endpoint.
    """

    object_id: Optional[str] = None
    status: Optional[str] = None
    substatus: Optional[ShippoSubstatus] = None
    status_details: Optional[str] = None
    status_date: Optional[datetime] = None
    location: Optional[ShippoLocation] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("status_date", mode="before")
    @classmethod
    def _ensure_utc(cls, v: datetime | str | None) -> datetime | None:
        """Normalise naive datetimes to UTC."""
        if v is None:
            return None
        if isinstance(v, str):
            v = datetime.fromisoformat(v)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class ShippoTrackingStatus(BaseModel):
    """Top-level tracking status from the Shippo API.

    Represents the ``tracking_status`` object embedded in the full
    tracking response.
    """

    object_id: Optional[str] = None
    status: Optional[str] = None
    substatus: Optional[ShippoSubstatus] = None
    status_details: Optional[str] = None
    status_date: Optional[datetime] = None
    location: Optional[ShippoLocation] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("status_date", mode="before")
    @classmethod
    def _ensure_utc(cls, v: datetime | str | None) -> datetime | None:
        """Normalise naive datetimes to UTC."""
        if v is None:
            return None
        if isinstance(v, str):
            v = datetime.fromisoformat(v)
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class ShippoTrackingResponse(BaseModel):
    """Full response from ``GET /tracks/{carrier}/{tracking_number}``.

    Contains the current tracking status plus the complete tracking
    history array.
    """

    carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    address_from: Optional[ShippoLocation] = None
    address_to: Optional[ShippoLocation] = None
    eta: Optional[datetime] = None
    original_eta: Optional[datetime] = None

    @field_validator("eta", "original_eta", mode="before")
    @classmethod
    def _parse_eta(cls, v: datetime | str | None) -> datetime | None:
        """Parse ETA from ISO string to datetime."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                v = datetime.fromisoformat(v)
            except ValueError:
                logger.warning(f"Could not parse ETA value: {v!r}")
                return None
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v

    servicelevel: Optional[dict] = None
    metadata: Optional[str] = None
    tracking_status: Optional[ShippoTrackingStatus] = None
    tracking_history: list[ShippoTrackingEvent] = []
    object_created: Optional[str] = None
    object_updated: Optional[str] = None
    object_id: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ShippoWebhookEvent(BaseModel):
    """Payload delivered to the Shippo webhook endpoint.

    ``event`` is typically ``"track_updated"`` for tracking webhooks.
    ``data`` contains a :class:`ShippoTrackingResponse`-shaped dict.
    """

    event: str
    data: dict

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Firestore persistence model (requires ``[firestore]`` extra)
# ---------------------------------------------------------------------------

_HAS_FIREDANTIC = False
_FiredanticBase: type = BaseModel  # fallback

try:
    from firedantic import Model as _FiredanticModel

    _HAS_FIREDANTIC = True
    _FiredanticBase = _FiredanticModel
except ImportError:
    pass


class ShippoTrackingDetail(_FiredanticBase):  # type: ignore[misc]
    """Persisted Shippo tracking detail.

    When firedantic is installed (via the ``[firestore]`` extra) this is a
    Firedantic ``Model`` stored in the ``shippo_tracking_details`` collection.
    Without firedantic it is a plain Pydantic ``BaseModel``.
    """

    if _HAS_FIREDANTIC:
        __collection__ = "shippo_tracking_details"

    tracking_number: str
    carrier: str

    status: Optional[str] = None
    substatus: Optional[ShippoSubstatus] = None
    status_details: Optional[str] = None
    status_date: Optional[datetime] = None

    eta: Optional[datetime] = None

    @field_validator("eta", mode="before")
    @classmethod
    def _parse_eta(cls, v: datetime | str | None) -> datetime | None:
        """Parse ETA from ISO string or existing Firestore string data to datetime."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            try:
                v = datetime.fromisoformat(v)
            except ValueError:
                logger.warning(f"Could not parse ETA value: {v!r}")
                return None
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v

    origin_city: Optional[str] = None
    origin_state: Optional[str] = None
    origin_zip: Optional[str] = None
    origin_country: Optional[str] = None

    destination_city: Optional[str] = None
    destination_state: Optional[str] = None
    destination_zip: Optional[str] = None
    destination_country: Optional[str] = None

    tracking_events: list[ShippoTrackingEvent] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(extra="allow")

    @classmethod
    def _validate_id(cls, values: dict) -> dict:
        """Ensure the document ID is the tracking number."""
        if not values.get("id"):
            values["id"] = values.get("tracking_number", "")
        return values

    def update_from_response(self, response: ShippoTrackingResponse) -> ShippoTrackingDetail:
        """Merge fresh API data into this persisted record."""
        if response.tracking_status:
            self.status = response.tracking_status.status
            self.substatus = response.tracking_status.substatus
            self.status_details = response.tracking_status.status_details
            self.status_date = response.tracking_status.status_date

        if response.address_from:
            self.origin_city = response.address_from.city
            self.origin_state = response.address_from.state
            self.origin_zip = response.address_from.zip
            self.origin_country = response.address_from.country

        if response.address_to:
            self.destination_city = response.address_to.city
            self.destination_state = response.address_to.state
            self.destination_zip = response.address_to.zip
            self.destination_country = response.address_to.country

        self.eta = response.eta
        self.tracking_events = [ShippoTrackingEvent(**event.model_dump()) for event in response.tracking_history]
        self.updated_at = datetime.now(UTC)
        return self
