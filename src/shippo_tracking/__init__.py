"""Shippo tracking client with optional Firestore persistence.

Install with ``pip install shippo-tracking[firestore]`` to enable
Firedantic persistence models and repository.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ShippoClient",
    "ShippoService",
    "ShippoTrackingDetail",
    "ShippoTrackingEvent",
    "ShippoTrackingResponse",
    "ShippoTrackingStatus",
    "ShippoTrackingStatusEnum",
    "ShippoWebhookEvent",
]


def __getattr__(name: str) -> Any:
    """Lazy attribute access — avoids import-time side effects."""
    if name == "ShippoClient":
        from .client import ShippoClient

        return ShippoClient
    if name == "ShippoService":
        from .service import ShippoService

        return ShippoService
    if name in {
        "ShippoTrackingDetail",
        "ShippoTrackingEvent",
        "ShippoTrackingResponse",
        "ShippoTrackingStatus",
        "ShippoTrackingStatusEnum",
        "ShippoWebhookEvent",
    }:
        from . import models

        return getattr(models, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
