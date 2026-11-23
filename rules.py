"""Deterministic routing policy for a classroom guest support service."""

import re
from dataclasses import dataclass


SAFETY_TYPES = frozenset({"lockout", "threat", "medical", "hazard"})
ROUTINE_FIELDS = {
    "refund": ("refund_status", "refund_amount", "refund_expected_at"),
    "checkout": ("checkout_at", "late_checkout_allowed", "key_return_instructions"),
    "checkin": ("checkin_at", "checkin_instructions_status", "entry_method"),
    "wifi": ("wifi_available", "wifi_help_reference"),
}


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str
    booking_fields: tuple[str, ...] = ()


def decide(
    intents: tuple[str, ...],
    booking_id: str | None,
    *,
    uncertain: bool = False,
    conflicting_booking: bool = False,
) -> Decision:
    """Select read-only fields after safety, identity, and uncertainty gates."""
    # Safety first, even when the reported message also contains a routine intent.
    if SAFETY_TYPES.intersection(intents):
        return Decision("escalate", "safety")
    if not booking_id or not re.fullmatch(r"HM[A-Z0-9]{8}", booking_id):
        return Decision("escalate", "missing_or_invalid_booking")
    if uncertain or conflicting_booking or not intents:
        return Decision("escalate", "requires_human_review")
    if any(intent not in ROUTINE_FIELDS for intent in intents):
        return Decision("escalate", "unknown_type")
    fields = dict.fromkeys(field for intent in intents for field in ROUTINE_FIELDS[intent])
    return Decision("auto_answer", "routine_verified_lookup_only", tuple(fields))
