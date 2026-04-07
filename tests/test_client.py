"""Unit tests for ShippoClient."""

import pytest

from shippo_tracking.client import ShippoClient

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
