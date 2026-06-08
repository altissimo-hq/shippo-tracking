"""Shippo tracking exception hierarchy."""


class ShippoError(Exception):
    """Base error for the shippo-tracking package."""


class ShippoTrackingDetailNotFoundError(ShippoError):
    """Raised when a tracking detail is not found in persistence."""


class ShippoClientError(ShippoError):
    """Error communicating with the Shippo API."""


class ShippoWebhookProcessingError(ShippoError):
    """Error processing a Shippo webhook event."""
