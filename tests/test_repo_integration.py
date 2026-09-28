"""Integration tests for ShippoRepo against the Firestore emulator.

Skipped unless FIRESTORE_EMULATOR_HOST is set, e.g.:

    firebase emulators:start --only firestore
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 poetry run pytest -m integration
"""

import os
import uuid

import pytest

from altissimo.shippo_tracking.exceptions import ShippoTrackingDetailNotFoundError
from altissimo.shippo_tracking.models import ShippoTrackingDetail
from altissimo.shippo_tracking.repo import ShippoRepo

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("FIRESTORE_EMULATOR_HOST"), reason="FIRESTORE_EMULATOR_HOST not set"),
]


@pytest.fixture
def repo():
    from firedantic.configurations import configuration
    from google.auth.credentials import AnonymousCredentials
    from google.cloud.firestore import Client

    # A unique collection prefix per test keeps runs isolated on a shared emulator
    client = Client(project="shippo-tracking-test", credentials=AnonymousCredentials())
    configuration.add(client=client, prefix=f"test-{uuid.uuid4().hex[:8]}-")
    yield ShippoRepo()
    ShippoTrackingDetail.delete_all()


def make_detail(tracking_number: str, status: str | None = None) -> ShippoTrackingDetail:
    return ShippoTrackingDetail(tracking_number=tracking_number, carrier="usps", status=status)


class TestShippoRepoIntegration:
    """Round-trips through real firedantic persistence."""

    def test_save_uses_tracking_number_as_document_id(self, repo):
        repo.save_tracking_detail(make_detail("TN123", "TRANSIT"))

        got = repo.get_tracking_detail("TN123")
        assert got.id == "TN123"
        assert got.status == "TRANSIT"

    def test_resaving_updates_instead_of_duplicating(self, repo):
        repo.save_tracking_detail(make_detail("TN123", "TRANSIT"))
        repo.save_tracking_detail(make_detail("TN123", "DELIVERED"))

        details = repo.list_tracking_details()
        assert [d.status for d in details] == ["DELIVERED"]

    def test_list_status_filters(self, repo):
        repo.save_tracking_detail(make_detail("TN1", "TRANSIT"))
        repo.save_tracking_detail(make_detail("TN2", "DELIVERED"))

        assert [d.tracking_number for d in repo.list_tracking_details(status="transit")] == ["TN1"]
        assert [d.tracking_number for d in repo.list_tracking_details(exclude_status="delivered")] == ["TN1"]

    def test_delete(self, repo):
        repo.save_tracking_detail(make_detail("TN123"))
        repo.delete_tracking_detail("TN123")

        with pytest.raises(ShippoTrackingDetailNotFoundError):
            repo.get_tracking_detail("TN123")

    def test_missing_detail_raises_not_found(self, repo):
        with pytest.raises(ShippoTrackingDetailNotFoundError):
            repo.get_tracking_detail("does-not-exist")
        with pytest.raises(ShippoTrackingDetailNotFoundError):
            repo.delete_tracking_detail("does-not-exist")
