"""Shippo tracking service.

All Shippo business logic lives here.  Dependencies (client, repo) are
injected via constructor for testability.

The ``on_delivery`` callback hook lets consuming projects define what
happens when a package is delivered (e.g. send an email, update an order)
without coupling this package to any specific project's domain.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

from .exceptions import ShippoTrackingDetailNotFoundError, ShippoWebhookProcessingError
from .models import (
    ShippoTrackingDetail,
    ShippoTrackingResponse,
    ShippoTrackingStatusEnum,
    ShippoWebhookEvent,
)
from .repo import ShippoRepo, ShippoRepoProtocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols for injectable dependencies
# ---------------------------------------------------------------------------


class ShippoClientProtocol(Protocol):
    """Protocol for the Shippo API client dependency."""

    def get_tracking_status(self, carrier: str, tracking_number: str) -> ShippoTrackingResponse: ...

    def register_tracking(self, carrier: str, tracking_number: str) -> ShippoTrackingResponse: ...


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ShippoService:
    """Shippo business logic and orchestration.

    Usage::

        # Production — lazily creates real client & repo
        service = ShippoService()

        # With delivery callback
        service = ShippoService(on_delivery=my_delivery_handler)

        # Testing — inject fakes
        service = ShippoService(client=fake_client, repo=fake_repo)
    """

    def __init__(
        self,
        *,
        client: ShippoClientProtocol | None = None,
        repo: ShippoRepoProtocol | None = None,
        on_delivery: Callable[[ShippoTrackingDetail], None] | None = None,
    ) -> None:
        self._client = client
        self._repo = repo
        self._on_delivery = on_delivery

    def _get_client(self) -> ShippoClientProtocol:
        if self._client is None:
            from .client import ShippoClient  # noqa: PLC0415

            self._client = ShippoClient()
        return self._client

    def _get_repo(self) -> ShippoRepoProtocol:
        if self._repo is None:
            self._repo = ShippoRepo()
        return self._repo

    # -----------------------------------------------------------------
    # Tracking operations
    # -----------------------------------------------------------------

    def get_tracking_status(self, carrier: str, tracking_number: str) -> ShippoTrackingResponse:
        """Fetch tracking status from the Shippo API.

        This only calls the API — it does not persist anything.
        """
        logger.info("Fetching tracking status for %s/%s", carrier, tracking_number)
        return self._get_client().get_tracking_status(carrier, tracking_number)

    def get_tracking_detail(self, tracking_number: str) -> ShippoTrackingDetail:
        """Get a persisted tracking detail from Firestore.

        Raises:
            ShippoTrackingDetailNotFoundError: If not found.
        """
        return self._get_repo().get_tracking_detail(tracking_number)

    def list_tracking_details(self) -> list[ShippoTrackingDetail]:
        """List all persisted tracking details."""
        return self._get_repo().list_tracking_details()

    def save_tracking_detail(self, carrier: str, tracking_number: str) -> ShippoTrackingDetail:
        """Fetch tracking from the Shippo API and persist to Firestore.

        If a record already exists for this tracking number it is updated
        in place; otherwise a new document is created.
        """
        response = self.get_tracking_status(carrier, tracking_number)

        repo = self._get_repo()
        try:
            detail = repo.get_tracking_detail(tracking_number)
            detail.update_from_response(response)
        except ShippoTrackingDetailNotFoundError:
            detail = ShippoTrackingDetail(
                id=tracking_number,
                tracking_number=tracking_number,
                carrier=carrier,
            )
            detail.update_from_response(response)

        repo.save_tracking_detail(detail)
        logger.info("Saved tracking detail for %s/%s [%s]", carrier, tracking_number, detail.status)
        return detail

    def delete_tracking_detail(self, tracking_number: str) -> dict:
        """Delete a persisted tracking detail.

        Raises:
            ShippoTrackingDetailNotFoundError: If not found.
        """
        self._get_repo().delete_tracking_detail(tracking_number)
        logger.info("Deleted tracking detail: %s", tracking_number)
        return {"id": tracking_number}

    def process_tracking_details(self) -> dict:
        """Re-fetch and persist all non-delivered tracking details.

        Iterates every persisted ``ShippoTrackingDetail`` record and skips any
        that already have status ``DELIVERED``.  All others are refreshed by
        calling ``save_tracking_detail`` (which upserts).

        Returns a summary dict with ``processed``, ``skipped``, and ``errors``
        counts.
        """
        details = self.list_tracking_details()
        processed = 0
        skipped = 0
        errors = 0
        for detail in sorted(details, key=lambda x: x.updated_at or x.created_at):
            if detail.status == ShippoTrackingStatusEnum.DELIVERED.value:
                skipped += 1
                continue
            try:
                self.save_tracking_detail(detail.carrier, detail.tracking_number)
                processed += 1
            except Exception:
                logger.exception("Error refreshing tracking detail %s", detail.tracking_number)
                errors += 1
        logger.info("process_tracking_details: processed=%d skipped=%d errors=%d", processed, skipped, errors)
        return {"status": "ok", "processed": processed, "skipped": skipped, "errors": errors}

    def register_tracking(self, carrier: str, tracking_number: str) -> ShippoTrackingResponse:
        """Register a tracking number with Shippo for webhook notifications.

        This tells Shippo to start sending ``track_updated`` webhook events
        for this shipment.  Safe to call multiple times — Shippo is
        idempotent.
        """
        logger.info("Registering tracking for webhooks: %s/%s", carrier, tracking_number)
        return self._get_client().register_tracking(carrier, tracking_number)

    def register_all_tracking(self) -> dict:
        """Register all non-delivered tracking numbers for webhook notifications.

        Returns a summary dict with ``registered``, ``skipped``, and
        ``errors`` counts.
        """
        details = self.list_tracking_details()
        registered = 0
        skipped = 0
        errors = 0
        for detail in sorted(details, key=lambda x: x.updated_at or x.created_at):
            if detail.status == ShippoTrackingStatusEnum.DELIVERED.value:
                skipped += 1
                continue
            try:
                self.register_tracking(detail.carrier, detail.tracking_number)
                registered += 1
            except Exception:
                logger.exception("Error registering tracking %s", detail.tracking_number)
                errors += 1
        logger.info("register_all_tracking: registered=%d skipped=%d errors=%d", registered, skipped, errors)
        return {"status": "ok", "registered": registered, "skipped": skipped, "errors": errors}

    # -----------------------------------------------------------------
    # Webhook processing
    # -----------------------------------------------------------------

    def process_webhook(self, payload: dict) -> dict:
        """Process an incoming Shippo webhook event.

        For ``track_updated`` events this persists tracking data and
        triggers the ``on_delivery`` callback if the status is ``DELIVERED``.
        """
        try:
            event = ShippoWebhookEvent(**payload)
        except Exception as e:
            raise ShippoWebhookProcessingError(f"Invalid webhook payload: {e}") from e

        logger.info("Processing Shippo webhook: %s", event.event)

        if event.event == "track_updated":
            return self._handle_track_updated(event)

        logger.info("Ignoring unhandled Shippo event type: %s", event.event)
        return {"status": "ignored", "event": event.event}

    def _handle_track_updated(self, event: ShippoWebhookEvent) -> dict:
        """Handle a ``track_updated`` webhook event."""
        tracking_response = ShippoTrackingResponse(**event.data)

        carrier = tracking_response.carrier or "unknown"
        tracking_number = tracking_response.tracking_number
        if not tracking_number:
            logger.warning("track_updated event missing tracking_number, skipping")
            return {"status": "skipped", "reason": "no tracking_number"}

        repo = self._get_repo()
        try:
            detail = repo.get_tracking_detail(tracking_number)
            detail.update_from_response(tracking_response)
        except ShippoTrackingDetailNotFoundError:
            detail = ShippoTrackingDetail(
                id=tracking_number,
                tracking_number=tracking_number,
                carrier=carrier,
            )
            detail.update_from_response(tracking_response)

        repo.save_tracking_detail(detail)
        logger.info("Updated tracking detail from webhook: %s/%s [%s]", carrier, tracking_number, detail.status)

        # Trigger delivery callback if delivered
        if detail.status == ShippoTrackingStatusEnum.DELIVERED.value and self._on_delivery:
            try:
                self._on_delivery(detail)
            except Exception:
                logger.exception("Error in on_delivery callback for %s", tracking_number)

        return {"status": "processed", "tracking_number": tracking_number}
