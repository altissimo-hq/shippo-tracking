"""Shippo webhook authentication helpers.

Shippo supports two request-level options (see
https://docs.goshippo.com/tracking/webhook-security):

* **Self-generated token** — a secret appended to the webhook URL as
  ``?token=<token>``, echoed back on every POST.
* **HMAC** — a ``Shippo-Auth-Signature`` header of the form
  ``t=<timestamp>,v1=<signature>``, where::

      signature = hex(HMAC-SHA256(secret, f"{timestamp}.{raw_body}"))
"""

from __future__ import annotations

import hashlib
import hmac
import time

SIGNATURE_HEADER = "Shippo-Auth-Signature"
TOKEN_PARAM = "token"  # noqa: S105 - query parameter name, not a secret


def verify_token(expected: str, received: str | None) -> bool:
    """Return ``True`` if ``received`` matches ``expected`` (constant-time)."""
    if not received:
        return False
    return hmac.compare_digest(expected.encode(), received.encode())


def _sign(secret: str, timestamp: str, body: bytes) -> str:
    message = timestamp.encode() + b"." + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def compute_signature_header(secret: str, body: bytes, timestamp: int | None = None) -> str:
    """Build a ``Shippo-Auth-Signature`` header value for ``body``.

    Useful for testing webhook endpoints with signed payloads.
    """
    ts = str(int(time.time()) if timestamp is None else timestamp)
    return f"t={ts},v1={_sign(secret, ts, body)}"


def verify_signature(
    secret: str,
    body: bytes,
    header: str | None,
    *,
    tolerance_seconds: int | None = None,
) -> bool:
    """Return ``True`` if ``header`` is a valid Shippo signature for ``body``.

    If ``tolerance_seconds`` is set, the header's timestamp must also be
    within that many seconds of the current time (replay protection).
    """
    if not header:
        return False

    parts: dict[str, str] = {}
    for item in header.split(","):
        key, sep, value = item.strip().partition("=")
        if sep:
            parts[key] = value

    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        return False

    if tolerance_seconds is not None:
        try:
            age = abs(time.time() - int(timestamp))
        except ValueError:
            return False
        if age > tolerance_seconds:
            return False

    return hmac.compare_digest(_sign(secret, timestamp, body), signature)
