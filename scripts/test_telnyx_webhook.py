#!/usr/bin/env python3
"""
Test script for the Telnyx webhook endpoint. Sends a sample Telnyx-style
payload to POST /api/sms/webhook/telnyx to exercise the store function.

Usage:
    python scripts/test_telnyx_webhook.py
    python scripts/test_telnyx_webhook.py --url http://localhost:8675
    python scripts/test_telnyx_webhook.py --event message.sent
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root so app can be imported if we need config
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)


def make_message_received(from_phone: str = "+13125550001", to_phone: str = "+17735550002", text: str = "Test SMS via webhook") -> dict:
    """Build a Telnyx message.received-style payload."""
    event_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+00:00"
    return {
        "data": {
            "event_type": "message.received",
            "id": event_id,
            "occurred_at": now,
            "payload": {
                "completed_at": None,
                "cost": {"amount": "0.0000", "currency": "USD"},
                "direction": "inbound",
                "encoding": "GSM-7",
                "errors": [],
                "from": {
                    "carrier": "T-Mobile USA",
                    "line_type": "long_code",
                    "phone_number": from_phone,
                },
                "id": message_id,
                "media": [],
                "messaging_profile_id": "740572b6-099c-44a1-89b9-6c92163bc68d",
                "organization_id": "47a530f8-4362-4526-829b-bcee17fd9f7a",
                "parts": 1,
                "received_at": now,
                "record_type": "message",
                "sent_at": None,
                "tags": [],
                "text": text,
                "to": [
                    {
                        "carrier": "Telnyx",
                        "line_type": "Wireless",
                        "phone_number": to_phone,
                        "status": "webhook_delivered",
                    }
                ],
                "type": "SMS",
                "valid_until": None,
                "webhook_failover_url": None,
                "webhook_url": "https://example.com/webhooks",
            },
            "record_type": "event",
        },
        "meta": {
            "attempt": 1,
            "delivered_to": "https://example.com/webhooks",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="POST a sample Telnyx webhook to the sms webhook endpoint")
    parser.add_argument(
        "--url",
        default="http://localhost:8675",
        help="Base URL of the API (default: http://localhost:8675)",
    )
    parser.add_argument(
        "--event",
        default="message.received",
        choices=("message.received", "message.sent", "message.finalized"),
        help="Event type to send (default: message.received)",
    )
    parser.add_argument("--from-phone", default="+13125550001", help="From phone number")
    parser.add_argument("--to-phone", default="+17735550002", help="To phone number")
    parser.add_argument("--text", default="Test SMS via webhook script", help="Message text")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print full request/response")
    args = parser.parse_args()

    payload = make_message_received(
        from_phone=args.from_phone,
        to_phone=args.to_phone,
        text=args.text,
    )
    if args.event != "message.received":
        payload["data"]["event_type"] = args.event
        payload["data"]["payload"]["direction"] = "outbound" if args.event != "message.received" else "inbound"

    endpoint = f"{args.url.rstrip('/')}/api/sms/webhook/telnyx"
    print(f"POST {endpoint}")
    if args.verbose:
        print("Body:", json.dumps(payload, indent=2))

    try:
        r = requests.post(endpoint, json=payload, timeout=10)
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return 1

    print(f"Status: {r.status_code}")
    try:
        body = r.json()
        print("Response:", json.dumps(body, indent=2))
    except Exception:
        print("Response (raw):", r.text)

    if r.status_code in (200, 201):
        print("OK — message stored in MongoDB 'sms' collection.")
        return 0
    print("Request did not succeed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
