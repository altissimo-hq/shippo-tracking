"""Unit tests for ShippoService."""

import pytest

from shippo_tracking.exceptions import (
    ShippoClientError,
    ShippoTrackingDetailNotFoundError,
    ShippoWebhookProcessingError,
)
from shippo_tracking.models import ShippoTrackingDetail
from shippo_tracking.service import ShippoService

pytestmark = pytest.mark.unit


class TestGetTrackingStatus:
    """Tests for ShippoService.get_tracking_status."""

    def test_returns_api_response(self, fake_client, fake_repo, sample_tracking_response):
        fake_client.add_response("usps", "9400111899223456789012", sample_tracking_response)
        service = ShippoService(client=fake_client, repo=fake_repo)

        result = service.get_tracking_status("usps", "9400111899223456789012")

        assert result.carrier == "usps"
        assert result.tracking_number == "9400111899223456789012"
        assert result.tracking_status.status == "TRANSIT"

    def test_raises_on_unknown_tracking(self, fake_client, fake_repo):
        service = ShippoService(client=fake_client, repo=fake_repo)

        with pytest.raises(ShippoClientError):
            service.get_tracking_status("usps", "nonexistent")


class TestSaveTrackingDetail:
    """Tests for ShippoService.save_tracking_detail."""

    def test_creates_new_detail(self, fake_client, fake_repo, sample_tracking_response):
        fake_client.add_response("usps", "9400111899223456789012", sample_tracking_response)
        service = ShippoService(client=fake_client, repo=fake_repo)

        result = service.save_tracking_detail("usps", "9400111899223456789012")

        assert result.tracking_number == "9400111899223456789012"
        assert result.carrier == "usps"
        assert result.status == "TRANSIT"
        assert "9400111899223456789012" in fake_repo._store

    def test_updates_existing_detail(self, fake_client, fake_repo, sample_tracking_response):
        # Pre-populate the repo
        existing = ShippoTrackingDetail(
            id="9400111899223456789012",
            tracking_number="9400111899223456789012",
            carrier="usps",
            status="PRE_TRANSIT",
        )
        fake_repo._store["9400111899223456789012"] = existing

        fake_client.add_response("usps", "9400111899223456789012", sample_tracking_response)
        service = ShippoService(client=fake_client, repo=fake_repo)

        result = service.save_tracking_detail("usps", "9400111899223456789012")

        assert result.status == "TRANSIT"
        assert result.updated_at is not None


class TestDeleteTrackingDetail:
    """Tests for ShippoService.delete_tracking_detail."""

    def test_deletes_existing(self, fake_client, fake_repo):
        fake_repo._store["TRACK123"] = ShippoTrackingDetail(
            id="TRACK123",
            tracking_number="TRACK123",
            carrier="usps",
        )
        service = ShippoService(client=fake_client, repo=fake_repo)

        result = service.delete_tracking_detail("TRACK123")

        assert result == {"id": "TRACK123"}
        assert "TRACK123" not in fake_repo._store

    def test_raises_on_missing(self, fake_client, fake_repo):
        service = ShippoService(client=fake_client, repo=fake_repo)

        with pytest.raises(ShippoTrackingDetailNotFoundError):
            service.delete_tracking_detail("nonexistent")


class TestProcessWebhook:
    """Tests for ShippoService.process_webhook."""

    def test_processes_track_updated(self, fake_client, fake_repo, sample_tracking_response):
        service = ShippoService(client=fake_client, repo=fake_repo)

        payload = {
            "event": "track_updated",
            "data": sample_tracking_response.model_dump(),
        }
        result = service.process_webhook(payload)

        assert result["status"] == "processed"
        assert result["tracking_number"] == "9400111899223456789012"
        assert "9400111899223456789012" in fake_repo._store

    def test_ignores_unknown_event(self, fake_client, fake_repo):
        service = ShippoService(client=fake_client, repo=fake_repo)

        result = service.process_webhook({"event": "transaction_updated", "data": {}})

        assert result["status"] == "ignored"
        assert len(fake_repo._store) == 0

    def test_raises_on_invalid_payload(self, fake_client, fake_repo):
        service = ShippoService(client=fake_client, repo=fake_repo)

        with pytest.raises(ShippoWebhookProcessingError):
            service.process_webhook({"bad": "data"})

    def test_skips_when_no_tracking_number(self, fake_client, fake_repo):
        service = ShippoService(client=fake_client, repo=fake_repo)

        payload = {
            "event": "track_updated",
            "data": {"carrier": "usps"},
        }
        result = service.process_webhook(payload)

        assert result["status"] == "skipped"


class TestListTrackingDetails:
    """Tests for ShippoService.list_tracking_details."""

    def test_returns_empty_list(self, fake_client, fake_repo):
        service = ShippoService(client=fake_client, repo=fake_repo)
        assert service.list_tracking_details() == []

    def test_returns_stored_details(self, fake_client, fake_repo):
        fake_repo._store["A"] = ShippoTrackingDetail(id="A", tracking_number="A", carrier="usps")
        fake_repo._store["B"] = ShippoTrackingDetail(id="B", tracking_number="B", carrier="fedex")
        service = ShippoService(client=fake_client, repo=fake_repo)

        result = service.list_tracking_details()

        assert len(result) == 2


class TestOnDeliveryCallback:
    """Tests for the on_delivery callback hook."""

    def test_callback_fires_on_delivered(self, fake_client, fake_repo, delivered_tracking_response):
        delivered_details = []

        def capture_delivery(detail: ShippoTrackingDetail):
            delivered_details.append(detail)

        service = ShippoService(client=fake_client, repo=fake_repo, on_delivery=capture_delivery)

        payload = {
            "event": "track_updated",
            "data": delivered_tracking_response.model_dump(),
        }
        result = service.process_webhook(payload)

        assert result["status"] == "processed"
        assert len(delivered_details) == 1
        assert delivered_details[0].status == "DELIVERED"

    def test_callback_not_fired_on_transit(self, fake_client, fake_repo, sample_tracking_response):
        delivered_details = []

        def capture_delivery(detail: ShippoTrackingDetail):
            delivered_details.append(detail)

        service = ShippoService(client=fake_client, repo=fake_repo, on_delivery=capture_delivery)

        payload = {
            "event": "track_updated",
            "data": sample_tracking_response.model_dump(),
        }
        service.process_webhook(payload)

        assert len(delivered_details) == 0

    def test_no_callback_when_not_set(self, fake_client, fake_repo, delivered_tracking_response):
        """Service works fine without an on_delivery callback."""
        service = ShippoService(client=fake_client, repo=fake_repo)

        payload = {
            "event": "track_updated",
            "data": delivered_tracking_response.model_dump(),
        }
        result = service.process_webhook(payload)

        assert result["status"] == "processed"

    def test_callback_error_does_not_break_processing(self, fake_client, fake_repo, delivered_tracking_response):
        """A failing callback should not prevent the webhook from being processed."""

        def broken_callback(detail: ShippoTrackingDetail):
            raise RuntimeError("Notification system is down")

        service = ShippoService(client=fake_client, repo=fake_repo, on_delivery=broken_callback)

        payload = {
            "event": "track_updated",
            "data": delivered_tracking_response.model_dump(),
        }
        result = service.process_webhook(payload)

        # Webhook still reports success — the tracking detail was saved
        assert result["status"] == "processed"
        assert "9400111899223456789012" in fake_repo._store


class TestStatusDowngradeProtection:
    """Tests for the 'never downgrade' guard (Issue #3).

    When USPS purges tracking data after ~90-120 days, the Shippo API
    returns PRE_TRANSIT for packages that were previously DELIVERED.
    The service must refuse to overwrite a higher-ranked status with
    a lower-ranked one.
    """

    def test_save_skips_downgrade(self, fake_client, fake_repo, pre_transit_tracking_response):
        """Existing DELIVERED record must not be overwritten by stale PRE_TRANSIT."""
        existing = ShippoTrackingDetail(
            id="9400111899223456789012",
            tracking_number="9400111899223456789012",
            carrier="usps",
            status="DELIVERED",
            status_details="Delivered to front door.",
        )
        fake_repo._store["9400111899223456789012"] = existing
        original_updated_at = existing.updated_at

        fake_client.add_response("usps", "9400111899223456789012", pre_transit_tracking_response)
        service = ShippoService(client=fake_client, repo=fake_repo)

        result = service.save_tracking_detail("usps", "9400111899223456789012")

        assert result.status == "DELIVERED"
        assert result.status_details == "Delivered to front door."
        assert result.updated_at == original_updated_at

    def test_save_allows_upgrade(self, fake_client, fake_repo, delivered_tracking_response):
        """A PRE_TRANSIT record must be upgradable to DELIVERED."""
        existing = ShippoTrackingDetail(
            id="9400111899223456789012",
            tracking_number="9400111899223456789012",
            carrier="usps",
            status="PRE_TRANSIT",
        )
        fake_repo._store["9400111899223456789012"] = existing

        fake_client.add_response("usps", "9400111899223456789012", delivered_tracking_response)
        service = ShippoService(client=fake_client, repo=fake_repo)

        result = service.save_tracking_detail("usps", "9400111899223456789012")

        assert result.status == "DELIVERED"
        assert result.updated_at is not None

    def test_save_creates_new_record(self, fake_client, fake_repo, pre_transit_tracking_response):
        """New records must be created normally even for PRE_TRANSIT."""
        fake_client.add_response("usps", "9400111899223456789012", pre_transit_tracking_response)
        service = ShippoService(client=fake_client, repo=fake_repo)

        result = service.save_tracking_detail("usps", "9400111899223456789012")

        assert result.tracking_number == "9400111899223456789012"
        assert result.status == "PRE_TRANSIT"
        assert "9400111899223456789012" in fake_repo._store

    def test_webhook_skips_downgrade(self, fake_client, fake_repo, pre_transit_tracking_response):
        """Webhook delivering PRE_TRANSIT for a DELIVERED record must be skipped."""
        existing = ShippoTrackingDetail(
            id="9400111899223456789012",
            tracking_number="9400111899223456789012",
            carrier="usps",
            status="DELIVERED",
            status_details="Delivered to front door.",
        )
        fake_repo._store["9400111899223456789012"] = existing

        service = ShippoService(client=fake_client, repo=fake_repo)
        payload = {
            "event": "track_updated",
            "data": pre_transit_tracking_response.model_dump(),
        }
        result = service.process_webhook(payload)

        assert result["status"] == "skipped"
        assert result["reason"] == "status_downgrade"
        assert fake_repo._store["9400111899223456789012"].status == "DELIVERED"

    def test_webhook_allows_upgrade(self, fake_client, fake_repo, delivered_tracking_response):
        """Webhook delivering DELIVERED for a TRANSIT record must update and fire on_delivery."""
        existing = ShippoTrackingDetail(
            id="9400111899223456789012",
            tracking_number="9400111899223456789012",
            carrier="usps",
            status="TRANSIT",
        )
        fake_repo._store["9400111899223456789012"] = existing

        delivered_details = []

        def capture_delivery(detail: ShippoTrackingDetail):
            delivered_details.append(detail)

        service = ShippoService(client=fake_client, repo=fake_repo, on_delivery=capture_delivery)
        payload = {
            "event": "track_updated",
            "data": delivered_tracking_response.model_dump(),
        }
        result = service.process_webhook(payload)

        assert result["status"] == "processed"
        assert fake_repo._store["9400111899223456789012"].status == "DELIVERED"
        assert len(delivered_details) == 1
