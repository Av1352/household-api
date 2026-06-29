"""
config.py — one place for settings and secrets.

Loads a local .env file if present (so you can run without exporting vars by
hand), but real environment variables always win, which is how hosting
platforms like Railway and Render inject secrets.
"""

import os


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            # setdefault: a real env var takes precedence over the file
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

# --- API ---
APP_TOKEN = os.environ.get("APP_TOKEN", "change-me")
DB_PATH = os.environ.get("DB_PATH", "household.db")

# --- WhatsApp Cloud API ---
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_RECIPIENT = os.environ.get("WHATSAPP_RECIPIENT", "")  # e.g. 9198XXXXXXXX
WHATSAPP_TEMPLATE = os.environ.get("WHATSAPP_TEMPLATE", "daily_household_summary")
WHATSAPP_LANG = os.environ.get("WHATSAPP_LANG", "en")
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v21.0")
