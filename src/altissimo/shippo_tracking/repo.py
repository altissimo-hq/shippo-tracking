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

    def list_tracking_details(
        self,
        *,
        status: str | None = None,
        exclude_status: str | None = None,
    ) -> list[ShippoTrackingDetail]: ...

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
            from firedantic import ModelNotFoundError

            try:
                detail: ShippoTrackingDetail = ShippoTrackingDetail.get_by_id(tracking_number)
            except ModelNotFoundError as e:
                raise ShippoTrackingDetailNotFoundError(f"Tracking detail not found: {tracking_number}") from e
        except ImportError as e:
            raise RuntimeError(
                "firedantic is required for ShippoRepo — install with: pip install shippo-tracking[firestore]"
            ) from e
        return detail

    def list_tracking_details(
        self,
        *,
        status: str | None = None,
        exclude_status: str | None = None,
    ) -> list[ShippoTrackingDetail]:
        """List tracking details, optionally filtered by status.

        Status values are matched case-insensitively.  If both ``status``
        and ``exclude_status`` are given, ``status`` wins.
        """
        details: list[ShippoTrackingDetail]
        if status:
            details = ShippoTrackingDetail.find({"status": status.upper()})
        elif exclude_status:
            details = ShippoTrackingDetail.find({"status": {"!=": exclude_status.upper()}})
        else:
            details = ShippoTrackingDetail.find()
        return details

    def save_tracking_detail(self, detail: ShippoTrackingDetail) -> None:
        """Save or update a tracking detail."""
        detail.save()

    def delete_tracking_detail(self, tracking_number: str) -> None:
        """Delete a tracking detail by tracking number.

        Raises:
            ShippoTrackingDetailNotFoundError: If the tracking detail does not exist.
        """
        try:
            from firedantic import ModelNotFoundError

            try:
                detail = ShippoTrackingDetail.get_by_id(tracking_number)
                detail.delete()
            except ModelNotFoundError as e:
                raise ShippoTrackingDetailNotFoundError(f"Tracking detail not found: {tracking_number}") from e
        except ImportError as e:
            raise RuntimeError(
                "firedantic is required for ShippoRepo — install with: pip install shippo-tracking[firestore]"
            ) from e
