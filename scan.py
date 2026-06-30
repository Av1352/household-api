"""
scan.py — read a grocery bill with Claude vision, server-side.

The Anthropic API key lives here (from the environment), never in the app.
The app uploads a photo; this returns a list of line items as plain dicts.
"""

import base64
import json

import requests

from config import ANTHROPIC_API_KEY, SCAN_MODEL

_PROMPT = """
You are reading a grocery shopping bill or receipt. Extract every purchased line item.
Respond with ONLY a JSON array, no markdown fences and no extra text.
Each element must be: {"name": string, "quantity": number, "unit": string, "price": number, "category": string}.
Rules:
- quantity is how many units were bought. If it is not shown, use 1.
- unit is like "kg", "g", "l", "ml", or "" for counted items such as eggs or soap bars.
- price is the total amount paid for that line, as a plain number.
- category must be exactly one of: Vegetables, Fruits, Dairy, Provisions, Spices, Snacks, Cleaning, Personal Care, Others.
- Skip totals, subtotals, taxes, discounts, and store details. Only real products.
""".strip()


def extract_items(image_bytes: bytes, media_type: str) -> list:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set on the server")

    b64 = base64.standard_b64encode(image_bytes).decode()

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": SCAN_MODEL,
            "max_tokens": 1500,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        },
        timeout=60,
    )

    if resp.status_code >= 400:
        raise RuntimeError(f"Vision API {resp.status_code}: {resp.text}")

    data = resp.json()
    text = "".join(
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    )
    cleaned = text.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)
