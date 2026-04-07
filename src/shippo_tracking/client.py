"""Shippo REST API client.

Handles HTTP calls to the Shippo tracking endpoints.
"""

from __future__ import annotations

import logging
import os

import requests

from .exceptions import ShippoClientError
from .models import ShippoTrackingResponse

logger = logging.getLogger(__name__)

SHIPPO_API_URL = "https://api.goshippo.com"


class ShippoClient:
    """Client for the Shippo REST API.

    The API key is resolved lazily from the ``SHIPPO_API_KEY`` environment
    variable.  A warning is logged (rather than crashing) if the key is
    missing — this keeps imports and construction safe in test and CI
    environments.

    Usage::

        client = ShippoClient()
        status = client.get_tracking_status("usps", "9400111…")

        # Or with explicit key
        client = ShippoClient(api_key="shippo_test_…")
    """

    def __init__(self, api_key: str | None = None, *, base_url: str = SHIPPO_API_URL) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @property
    def api_key(self) -> str:
        """Resolve the API key lazily."""
        if self._api_key is None:
            self._api_key = os.environ.get("SHIPPO_API_KEY", "")
        if not self._api_key:
            logger.warning("SHIPPO_API_KEY is not set.")
        return self._api_key

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"ShippoToken {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_tracking_status(self, carrier: str, tracking_number: str) -> ShippoTrackingResponse:
        """Fetch tracking status from the Shippo API.

        Args:
            carrier: Carrier token (e.g. ``"usps"``, ``"fedex"``).
            tracking_number: The tracking number.

        Returns:
            A typed :class:`ShippoTrackingResponse`.

        Raises:
            ShippoClientError: On any HTTP or parsing error.
        """
        url = f"{self._base_url}/tracks/{carrier}/{tracking_number}"
        logger.info("Requesting tracking status: %s/%s", carrier, tracking_number)

        try:
            response = requests.get(url, headers=self._headers, timeout=15)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ShippoClientError(f"Error fetching tracking status for {carrier}/{tracking_number}: {e}") from e

        try:
            return ShippoTrackingResponse(**response.json())
        except Exception as e:
            raise ShippoClientError(f"Error parsing tracking response for {carrier}/{tracking_number}: {e}") from e

    def register_tracking(self, carrier: str, tracking_number: str) -> ShippoTrackingResponse:
        """Register a tracking number for webhook notifications.

        Posts to ``/tracks/`` which tells Shippo to start sending
        ``track_updated`` webhook events for this shipment.  This is
        required for shipments created before the webhook was configured,
        or for shipments created outside of Shippo.

        Args:
            carrier: Carrier token (e.g. ``"usps"``).
            tracking_number: The tracking number.

        Returns:
            A typed :class:`ShippoTrackingResponse` with the current status.

        Raises:
            ShippoClientError: On any HTTP or parsing error.
        """
        url = f"{self._base_url}/tracks/"
        logger.info("Registering tracking for webhooks: %s/%s", carrier, tracking_number)

        try:
            response = requests.post(
                url,
                headers=self._headers,
                json={"carrier": carrier, "tracking_number": tracking_number},
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise ShippoClientError(f"Error registering tracking for {carrier}/{tracking_number}: {e}") from e

        try:
            return ShippoTrackingResponse(**response.json())
        except Exception as e:
            raise ShippoClientError(f"Error parsing registration response for {carrier}/{tracking_number}: {e}") from e
