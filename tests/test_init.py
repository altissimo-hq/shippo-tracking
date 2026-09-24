"""Regression tests for the package's public import surface.

The README documents ``from altissimo.shippo_tracking import ...`` for these
names (see #13, where documented imports were wrong).  These tests make sure
those documented imports keep resolving to the real classes.
"""

import pytest

import altissimo.shippo_tracking as pkg
from altissimo.shippo_tracking import client, models, service

pytestmark = pytest.mark.unit


class TestLazyExports:
    """Names exported lazily via altissimo.shippo_tracking.__getattr__."""

    def test_client(self):
        assert pkg.ShippoClient is client.ShippoClient

    def test_service(self):
        assert pkg.ShippoService is service.ShippoService

    @pytest.mark.parametrize(
        "name",
        [
            "ShippoTrackingDetail",
            "ShippoTrackingEvent",
            "ShippoTrackingResponse",
            "ShippoTrackingStatus",
            "ShippoTrackingStatusEnum",
            "ShippoWebhookEvent",
        ],
    )
    def test_models(self, name):
        assert getattr(pkg, name) is getattr(models, name)

    def test_unknown_attribute(self):
        with pytest.raises(AttributeError, match="has no attribute 'Nope'"):
            pkg.Nope  # noqa: B018
