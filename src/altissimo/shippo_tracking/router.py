"""Shippo webhook FastAPI router.

Thin adapter — delegates all business logic to
:class:`~shippo_tracking.service.ShippoService`.

Note: This router has no prefix — the service domain
(``shippo[-env].example.com``) already provides the namespace.  Services
that include this router should pass ``prefix="/shippo"`` at
``include_router()`` time if needed.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request

from .service import ShippoService
from .webhook import SIGNATURE_HEADER, TOKEN_PARAM, verify_signature, verify_token

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from .models import ShippoTrackingDetail

logger = logging.getLogger(__name__)


def create_shippo_router(
    *,
    on_delivery: Callable[[ShippoTrackingDetail], None] | None = None,
    tags: Sequence[str] | None = None,
    webhook_token: str | None = None,
    webhook_secret: str | None = None,
    signature_tolerance_seconds: int | None = None,
    service: ShippoService | None = None,
) -> APIRouter:
    """Create a Shippo webhook router with an optional delivery callback.

    This factory function lets consuming projects inject their own
    ``on_delivery`` handler when wiring up their FastAPI app::

        from altissimo.shippo_tracking.router import create_shippo_router

        def handle_delivery(detail):
            # project-specific notification logic
            ...

        app.include_router(create_shippo_router(on_delivery=handle_delivery))

    If ``webhook_token`` is set, every request must carry a matching
    ``?token=`` query parameter (Shippo's "self-generated token" option,
    configured by appending it to the webhook URL in the Shippo dashboard)
    or it is rejected with 401.

    If ``webhook_secret`` is set, every request must carry a valid
    ``Shippo-Auth-Signature`` HMAC header or it is rejected with 401.
    ``signature_tolerance_seconds`` additionally rejects signatures whose
    timestamp is too old.  Pass ``service`` to supply a preconfigured
    :class:`ShippoService` (``on_delivery`` is then ignored).
    """
    router = APIRouter(tags=list(tags) if tags else ["Shippo"])
    if service is None:
        service = ShippoService(on_delivery=on_delivery)

    @router.post("/webhook")
    async def shippo_webhook(request: Request) -> dict[str, Any]:
        """Handle incoming Shippo webhook events."""
        if webhook_token is not None and not verify_token(webhook_token, request.query_params.get(TOKEN_PARAM)):
            logger.warning("Rejected Shippo webhook with missing or invalid token")
            raise HTTPException(status_code=401, detail="Invalid webhook token")

        body = await request.body()
        if webhook_secret is not None and not verify_signature(
            webhook_secret,
            body,
            request.headers.get(SIGNATURE_HEADER),
            tolerance_seconds=signature_tolerance_seconds,
        ):
            logger.warning("Rejected Shippo webhook with missing or invalid signature")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        try:
            payload = json.loads(body)
            logger.info("Received Shippo webhook: %s", payload.get("event", "unknown"))

            result = service.process_webhook(payload)
            return result
        except Exception as e:
            logger.exception("Error processing Shippo webhook")
            raise HTTPException(status_code=500, detail="Error processing webhook") from e

    return router


# Convenience: a plain router with no delivery callback for simple setups
router = create_shippo_router()
