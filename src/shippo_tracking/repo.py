"""Shippo tracking persistence repository.

Requires the ``[firestore]`` extra (firedantic).
"""

from __future__ import annotations

from typing import Protocol

from .exceptions import ShippoTrackingDetailNotFoundError
from .models import ShippoTrackingDetail


class ShippoRepoProtocol(Protocol):
    """Protocol for Shippo persistence — implement for test fakes."""

    def get_tracking_detail(self, tracking_number: str) -> ShippoTrackingDetail: ...

    def list_tracking_details(self) -> list[ShippoTrackingDetail]: ...

    def save_tracking_detail(self, detail: ShippoTrackingDetail) -> None: ...

    def delete_tracking_detail(self, tracking_number: str) -> None: ...


class ShippoRepo:
    """Thin Firedantic persistence wrapper for Shippo tracking details.

    Requires firedantic to be installed (the ``[firestore]`` extra).
    """

    def get_tracking_detail(self, tracking_number: str) -> ShippoTrackingDetail:
        """Get a tracking detail by tracking number.

        Raises:
            ShippoTrackingDetailNotFoundError: If the tracking detail does not exist.
        """
        try:
            from firedantic import ModelNotFoundError  # noqa: PLC0415

            try:
                return ShippoTrackingDetail.get_by_id(tracking_number)
            except ModelNotFoundError as e:
                raise ShippoTrackingDetailNotFoundError(f"Tracking detail not found: {tracking_number}") from e
        except ImportError as e:
            raise RuntimeError(
                "firedantic is required for ShippoRepo — install with: pip install shippo-tracking[firestore]"
            ) from e

    def list_tracking_details(self) -> list[ShippoTrackingDetail]:
        """List all tracking details."""
        return ShippoTrackingDetail.find()

    def save_tracking_detail(self, detail: ShippoTrackingDetail) -> None:
        """Save or update a tracking detail."""
        detail.save()

    def delete_tracking_detail(self, tracking_number: str) -> None:
        """Delete a tracking detail by tracking number.

        Raises:
            ShippoTrackingDetailNotFoundError: If the tracking detail does not exist.
        """
        try:
            from firedantic import ModelNotFoundError  # noqa: PLC0415

            try:
                detail = ShippoTrackingDetail.get_by_id(tracking_number)
                detail.delete()
            except ModelNotFoundError as e:
                raise ShippoTrackingDetailNotFoundError(f"Tracking detail not found: {tracking_number}") from e
        except ImportError as e:
            raise RuntimeError(
                "firedantic is required for ShippoRepo — install with: pip install shippo-tracking[firestore]"
            ) from e
