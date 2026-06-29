"""
send_daily.py — the 9am run.

Reads the current data, builds Amma's morning summary using the same brain the
API uses, and sends it via WhatsApp. Runs once and exits, so it is meant to be
triggered by your host's scheduler (Railway/Render cron) at 9am India time.

Run manually to test:
    python send_daily.py            # actually sends
    python send_daily.py --dry-run  # prints the message, sends nothing
"""

import sys

import core
import db
from whatsapp import send_template


def build_message() -> str:
    items = db.all_items()
    bills = db.all_bills()

    buy = [i["name"] for i in core.compute_to_buy(items)]
    pay = core.compute_to_pay(bills)

    parts = []
    if buy:
        parts.append("Buy: " + ", ".join(buy))
    if pay:
        pay_bits = []
        for b in pay:
            d = b["days_until"]
            if d < 0:
                pay_bits.append(f"{b['name']} overdue")
            elif d == 0:
                pay_bits.append(f"{b['name']} due today")
            else:
                pay_bits.append(f"{b['name']} due in {d} days")
        parts.append("Pay: " + ", ".join(pay_bits))

    if not parts:
        return "Nothing urgent today. Have a lovely day!"

    message = "  ".join(parts)
    # Keep within a safe length for a template variable.
    return message[:900]


def main() -> None:
    db.init_db()
    message = build_message()
    dry_run = "--dry-run" in sys.argv

    print("Message:", message)
    if dry_run:
        print("(dry run, nothing sent)")
        return

    resp = send_template([message])
    print("Sent. Response:", resp)


if __name__ == "__main__":
    main()
