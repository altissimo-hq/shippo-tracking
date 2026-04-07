"""Shippo webhook FastAPI router.

Thin adapter — delegates all business logic to
:class:`~shippo_tracking.service.ShippoService`.

Note: This router has no prefix — the service domain
(``shippo[-env].example.com``) already provides the namespace.  Services
that include this router should pass ``prefix="/shippo"`` at
``include_router()`` time if needed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from fastapi import APIRouter, HTTPException, Request

from .models import ShippoTrackingDetail
from .service import ShippoService

logger = logging.getLogger(__name__)


def create_shippo_router(
    *,
    on_delivery: Callable[[ShippoTrackingDetail], None] | None = None,
    tags: Sequence[str] | None = None,
) -> APIRouter:
    """Create a Shippo webhook router with an optional delivery callback.

    This factory function lets consuming projects inject their own
    ``on_delivery`` handler when wiring up their FastAPI app::

        from shippo_tracking.router import create_shippo_router

        def handle_delivery(detail):
            # project-specific notification logic
            ...

        app.include_router(create_shippo_router(on_delivery=handle_delivery))
    """
    router = APIRouter(tags=list(tags) if tags else ["Shippo"])
    service = ShippoService(on_delivery=on_delivery)

    @router.post("/webhook")
    async def shippo_webhook(request: Request) -> dict:
        """Handle incoming Shippo webhook events."""
        try:
            payload = await request.json()
            logger.info("Received Shippo webhook: %s", payload.get("event", "unknown"))

            result = service.process_webhook(payload)
            return result
        except Exception as e:
            logger.exception("Error processing Shippo webhook")
            raise HTTPException(status_code=500, detail="Error processing webhook") from e

    return router


# Convenience: a plain router with no delivery callback for simple setups
router = create_shippo_router()
