# shippo-tracking

Shippo shipping & tracking client with optional Firestore persistence.

## Installation

```bash
# Basic (API client + models only)
pip install git+https://github.com/altissimo-io/shippo-tracking.git

# With Firestore persistence
pip install "shippo-tracking[firestore] @ git+https://github.com/altissimo-io/shippo-tracking.git"
```

## Quick Start

```python
from shippo_tracking import ShippoClient

client = ShippoClient()  # reads SHIPPO_API_KEY from env
status = client.get_tracking_status("usps", "9400111899223456789012")
print(status.tracking_status.status)  # "TRANSIT", "DELIVERED", etc.
```

## With Firestore Persistence

```python
from shippo_tracking import ShippoService

service = ShippoService()

# Fetch from API and save to Firestore
detail = service.save_tracking_detail("usps", "9400111899223456789012")

# Register for webhook notifications
service.register_tracking("usps", "9400111899223456789012")
```

## Delivery Callback Hook

Inject your own logic for when a package is delivered:

```python
from shippo_tracking import ShippoService, ShippoTrackingDetail

def handle_delivery(detail: ShippoTrackingDetail):
    print(f"Package {detail.tracking_number} delivered!")
    # Send email, update order, notify team, etc.

service = ShippoService(on_delivery=handle_delivery)
```

## Status Downgrade Protection

The service guards against **status regression**. Tracking statuses have a natural
lifecycle ordering:

```text
UNKNOWN → PRE_TRANSIT → TRANSIT → DELIVERED → RETURNED → FAILURE
```

If a persisted record already has a status further along in this progression (e.g.
`DELIVERED`), and the Shippo API or a webhook returns a lower status (e.g.
`PRE_TRANSIT` — common when USPS purges old tracking data), the update is
**silently skipped** and the existing record is preserved.

This applies to both `save_tracking_detail()` and incoming webhook events.

## FastAPI Webhook Router

```python
from fastapi import FastAPI
from shippo_tracking.router import create_shippo_router

app = FastAPI()

# Simple — no delivery callback
app.include_router(create_shippo_router())

# With delivery callback
app.include_router(create_shippo_router(on_delivery=handle_delivery))
```

## Testing

```bash
poetry install --with dev
poetry run pytest -v
```

All unit tests use in-memory fakes — no Firestore or network access required.
