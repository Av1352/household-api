"""
whatsapp.py — send a message through Meta's WhatsApp Cloud API.

Business-initiated messages (a scheduled 9am summary is one) must use a
pre-approved template. We use a single template with one body variable that
carries the whole summary line, which keeps Meta's approval simple.

Template to submit in Meta's WhatsApp Manager (category: Utility):
    Name: daily_household_summary
    Language: English
    Body: Good morning Amma. {{1}}
    Sample for {{1}}: Buy: rice, atta. Pay: car insurance due in 3 days.
"""

import requests

from config import (
    GRAPH_API_VERSION,
    WHATSAPP_LANG,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_RECIPIENT,
    WHATSAPP_TEMPLATE,
    WHATSAPP_TOKEN,
)


def _require_config() -> None:
    missing = [
        name
        for name, val in (
            ("WHATSAPP_TOKEN", WHATSAPP_TOKEN),
            ("WHATSAPP_PHONE_NUMBER_ID", WHATSAPP_PHONE_NUMBER_ID),
            ("WHATSAPP_RECIPIENT", WHATSAPP_RECIPIENT),
        )
        if not val
    ]
    if missing:
        raise RuntimeError(
            "WhatsApp is not configured. Missing: " + ", ".join(missing)
        )


def send_template(body_params: list) -> dict:
    """Send the approved template, filling its {{n}} body variables in order."""
    _require_config()

    url = (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}"
        f"/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": WHATSAPP_RECIPIENT,
        "type": "template",
        "template": {
            "name": WHATSAPP_TEMPLATE,
            "language": {"code": WHATSAPP_LANG},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(p)} for p in body_params
                    ],
                }
            ],
        },
    }
    resp = requests.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
        timeout=30,
    )
    if resp.status_code >= 400:
        # Surface Meta's error body, which is far more useful than a bare 400.
        raise RuntimeError(f"WhatsApp send failed {resp.status_code}: {resp.text}")
    return resp.json()
