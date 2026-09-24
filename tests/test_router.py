"""Unit tests for the Shippo webhook router and signature helpers."""

import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from altissimo.shippo_tracking.router import create_shippo_router
from altissimo.shippo_tracking.service import ShippoService
from altissimo.shippo_tracking.webhook import SIGNATURE_HEADER, compute_signature_header, verify_signature

pytestmark = pytest.mark.unit

SECRET = "test-secret"
TOKEN = "test-token-123abc"
BODY = json.dumps({"event": "track_updated", "data": {"carrier": "usps", "tracking_number": "TRACK123"}}).encode()


def make_client(fake_client, fake_repo, **kwargs) -> TestClient:
    app = FastAPI()
    service = ShippoService(client=fake_client, repo=fake_repo)
    app.include_router(create_shippo_router(service=service, **kwargs))
    return TestClient(app)


class TestVerifySignature:
    """Tests for the HMAC signature helpers."""

    def test_round_trip(self):
        header = compute_signature_header(SECRET, BODY)
        assert verify_signature(SECRET, BODY, header)

    def test_wrong_secret(self):
        header = compute_signature_header("other", BODY)
        assert not verify_signature(SECRET, BODY, header)

    def test_tampered_body(self):
        header = compute_signature_header(SECRET, BODY)
        assert not verify_signature(SECRET, BODY + b" ", header)

    @pytest.mark.parametrize("header", [None, "", "garbage", "t=123", "v1=abc"])
    def test_malformed_header(self, header):
        assert not verify_signature(SECRET, BODY, header)

    def test_expired_timestamp(self):
        header = compute_signature_header(SECRET, BODY, timestamp=1)
        assert verify_signature(SECRET, BODY, header)
        assert not verify_signature(SECRET, BODY, header, tolerance_seconds=300)


class TestWebhookRoute:
    """Tests for the /webhook route."""

    def test_no_secret_accepts_unsigned(self, fake_client, fake_repo):
        client = make_client(fake_client, fake_repo)
        resp = client.post("/webhook", content=BODY)
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"

    def test_secret_rejects_missing_signature(self, fake_client, fake_repo):
        client = make_client(fake_client, fake_repo, webhook_secret=SECRET)
        resp = client.post("/webhook", content=BODY)
        assert resp.status_code == 401
        assert fake_repo._store == {}

    def test_secret_rejects_bad_signature(self, fake_client, fake_repo):
        client = make_client(fake_client, fake_repo, webhook_secret=SECRET)
        header = compute_signature_header("wrong", BODY)
        resp = client.post("/webhook", content=BODY, headers={SIGNATURE_HEADER: header})
        assert resp.status_code == 401
        assert fake_repo._store == {}

    def test_secret_accepts_valid_signature(self, fake_client, fake_repo):
        client = make_client(fake_client, fake_repo, webhook_secret=SECRET)
        header = compute_signature_header(SECRET, BODY)
        resp = client.post("/webhook", content=BODY, headers={SIGNATURE_HEADER: header})
        assert resp.status_code == 200
        assert "TRACK123" in fake_repo._store

    def test_matches_shippo_bash_reference(self):
        # Same computation as Shippo's documented bash check:
        # echo -n "${timestamp}.${payload}" | openssl dgst -sha256 -hmac "${secret}"
        expected = hmac.new(SECRET.encode(), b"1688493073." + BODY, hashlib.sha256).hexdigest()
        assert compute_signature_header(SECRET, BODY, timestamp=1688493073) == f"t=1688493073,v1={expected}"


class TestWebhookToken:
    """Tests for the self-generated ?token= option."""

    @pytest.mark.parametrize("url", ["/webhook", "/webhook?token=wrong", "/webhook?token="])
    def test_rejects_missing_or_wrong_token(self, fake_client, fake_repo, url):
        client = make_client(fake_client, fake_repo, webhook_token=TOKEN)
        resp = client.post(url, content=BODY)
        assert resp.status_code == 401
        assert fake_repo._store == {}

    def test_accepts_valid_token(self, fake_client, fake_repo):
        client = make_client(fake_client, fake_repo, webhook_token=TOKEN)
        resp = client.post(f"/webhook?token={TOKEN}", content=BODY)
        assert resp.status_code == 200
        assert "TRACK123" in fake_repo._store

    def test_token_and_secret_both_required(self, fake_client, fake_repo):
        client = make_client(fake_client, fake_repo, webhook_token=TOKEN, webhook_secret=SECRET)
        header = compute_signature_header(SECRET, BODY)

        assert client.post(f"/webhook?token={TOKEN}", content=BODY).status_code == 401
        assert client.post("/webhook", content=BODY, headers={SIGNATURE_HEADER: header}).status_code == 401
        resp = client.post(f"/webhook?token={TOKEN}", content=BODY, headers={SIGNATURE_HEADER: header})
        assert resp.status_code == 200
