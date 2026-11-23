"""Emit a PostgreSQL insert statement for the course mock table.

Only read-only response fields are imported. Wi-Fi and door codes are omitted.
"""

import csv
import re
import sys
from datetime import date, time
from decimal import Decimal


def sql_literal(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, Decimal)):
        return str(value)
    return "'" + value.replace("'", "''") + "'"


def booking_values(position, row):
    booking = row["booking_id"]
    if not re.fullmatch(r"HM[A-Z0-9]{8}", booking):
        raise ValueError(f"Invalid booking ID in fixture row {position}")
    checkin = f"{date.fromisoformat(row['check_in_date']).isoformat()} {time.fromisoformat(row['check_in_time']).strftime('%H:%M')}"
    checkout = f"{date.fromisoformat(row['check_out_date']).isoformat()} {time.fromisoformat(row['check_out_time']).strftime('%H:%M')}"
    amount = Decimal(row["refund_amount"]) if row["refund_amount"] else None
    return (
        position, booking, checkin, checkout, row["refund_status"] or None, amount,
        row["refund_currency"] or None, bool(row["wifi_network"] and row["wifi_password"]),
        "Open the Wi-Fi guide in the authenticated reservation.",
        "Available in the authenticated reservation" if row["checkin_code"] else "Requires support",
        row["listing_city"],
    )


def main(source):
    with open(source, encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if len(rows) != 50:
        raise ValueError("Expected 50 course booking rows")
    values = [
        "(" + ", ".join(sql_literal(value) for value in booking_values(i, row)) + ")"
        for i, row in enumerate(rows, start=1)
    ]
    print("insert into public.airbnb_course_bookings values\n" + ",\n".join(values) + ";")


if __name__ == "__main__":
    main(sys.argv[1])
