"""Unit tests for ShippoClient."""

import pytest
import requests

from altissimo.shippo_tracking.client import ShippoClient
from altissimo.shippo_tracking.exceptions import ShippoClientError

pytestmark = pytest.mark.unit


class TestShippoClientInit:
    """Tests for ShippoClient construction."""

    def test_default_construction(self):
        client = ShippoClient()
        assert client._base_url == "https://api.goshippo.com"
        assert client._api_key is None

    def test_explicit_api_key(self):
        client = ShippoClient(api_key="test_key")
        assert client.api_key == "test_key"

    def test_custom_base_url(self):
        client = ShippoClient(base_url="https://custom.api.com/")
        assert client._base_url == "https://custom.api.com"

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("SHIPPO_API_KEY", "env_key_123")
        client = ShippoClient()
        assert client.api_key == "env_key_123"

    def test_missing_api_key_logs_warning(self, caplog, monkeypatch):
        monkeypatch.delenv("SHIPPO_API_KEY", raising=False)
        client = ShippoClient()
        with caplog.at_level("WARNING"):
            key = client.api_key
        assert key == ""
        assert "SHIPPO_API_KEY is not set" in caplog.text

    def test_headers_include_auth(self):
        client = ShippoClient(api_key="shippo_test_abc")
        headers = client._headers
        assert headers["Authorization"] == "ShippoToken shippo_test_abc"
        assert headers["Content-Type"] == "application/json"


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, payload=None, *, status_error: Exception | None = None, json_error: Exception | None = None):
        self._payload = payload
        self._status_error = status_error
        self._json_error = json_error

    def raise_for_status(self):
        if self._status_error:
            raise self._status_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


TRACKING_PAYLOAD = {
    "carrier": "usps",
    "tracking_number": "TRACK123",
    "tracking_status": {"status": "TRANSIT"},
}


class TestGetTrackingStatus:
    """Tests for ShippoClient.get_tracking_status HTTP handling."""

    def test_success(self, monkeypatch):
        calls = []

        def fake_get(url, headers, timeout):
            calls.append((url, headers, timeout))
            return FakeResponse(TRACKING_PAYLOAD)

        monkeypatch.setattr(requests, "get", fake_get)
        client = ShippoClient(api_key="k", base_url="https://api.example.com")

        result = client.get_tracking_status("usps", "TRACK123")

        assert result.tracking_status.status == "TRANSIT"
        assert calls == [("https://api.example.com/tracks/usps/TRACK123", client._headers, 15)]

    def test_http_error(self, monkeypatch):
        monkeypatch.setattr(
            requests, "get", lambda *a, **kw: FakeResponse(status_error=requests.HTTPError("404 Not Found"))
        )
        with pytest.raises(ShippoClientError, match="Error fetching tracking status"):
            ShippoClient(api_key="k").get_tracking_status("usps", "TRACK123")

    def test_parse_error(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse(json_error=ValueError("bad json")))
        with pytest.raises(ShippoClientError, match="Error parsing tracking response"):
            ShippoClient(api_key="k").get_tracking_status("usps", "TRACK123")


class TestRegisterTracking:
    """Tests for ShippoClient.register_tracking HTTP handling."""

    def test_success(self, monkeypatch):
        calls = []

        def fake_post(url, headers, json, timeout):
            calls.append((url, json))
            return FakeResponse(TRACKING_PAYLOAD)

        monkeypatch.setattr(requests, "post", fake_post)

        result = ShippoClient(api_key="k", base_url="https://api.example.com").register_tracking("usps", "TRACK123")

        assert result.tracking_number == "TRACK123"
        assert calls == [("https://api.example.com/tracks/", {"carrier": "usps", "tracking_number": "TRACK123"})]

    def test_http_error(self, monkeypatch):
        monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResponse(status_error=requests.ConnectionError()))
        with pytest.raises(ShippoClientError, match="Error registering tracking"):
            ShippoClient(api_key="k").register_tracking("usps", "TRACK123")

    def test_parse_error(self, monkeypatch):
        monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResponse(json_error=ValueError("bad json")))
        with pytest.raises(ShippoClientError, match="Error parsing registration response"):
            ShippoClient(api_key="k").register_tracking("usps", "TRACK123")
