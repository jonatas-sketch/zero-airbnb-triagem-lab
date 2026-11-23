"""Course prototype API, bound to localhost for authorized fixture checks."""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from classify import classify
from danger import DangerDetector, SentenceEncoder
from rules import SAFETY_TYPES, decide
from triage_config import DANGER_REVIEW_FLOOR, DANGER_THRESHOLD

app = FastAPI(title="Guest Support Triage")
logger = logging.getLogger(__name__)
BOOKING_COLUMNS = {
    "refund": ("refund_status", "refund_amount", "refund_currency"),
    "checkout": ("checkout_at",),
    "checkin": ("checkin_at", "checkin_instructions_status"),
    "wifi": ("wifi_available", "wifi_help_reference"),
}


class TriageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1, max_length=80)
    booking_id: str | None = Field(default=None, max_length=30)
    listing_city: str | None = Field(default=None, max_length=120)
    subject: str = Field(default="", max_length=300)
    message_body: str = Field(min_length=1, max_length=3500)


class TriageResult(BaseModel):
    message_id: str
    decision: Literal["auto_answer", "escalate"]
    reason: str
    matched_rule: str
    danger_score: float | None


@lru_cache
def detector():
    return DangerDetector.from_course_examples(
        SentenceEncoder(), Path(os.environ["DANGER_EXAMPLES_PATH"])
    )


def read_booking(booking_id: str, columns: tuple[str, ...], expected_city: str | None) -> dict:
    """Read only the allowlisted fixture fields from a localhost booking table."""
    url = os.environ["SUPABASE_URL"].rstrip("/")
    headers = {"Authorization": f"Bearer {os.environ['SUPABASE_BOOKINGS_KEY']}"}
    if publishable_key := os.getenv("SUPABASE_PUBLISHABLE_KEY"):
        headers["apikey"] = publishable_key
    fields = (*columns, "listing_city")
    response = httpx.get(
        f"{url}/rest/v1/airbnb_course_bookings",
        headers=headers,
        params={"booking_id": f"eq.{booking_id}", "select": ",".join(fields), "limit": 2},
        timeout=10.0,
    )
    response.raise_for_status()
    rows = response.json()
    if len(rows) != 1 or any(rows[0].get(column) in (None, "") for column in fields):
        raise ValueError("Missing or ambiguous facts")
    if expected_city and rows[0]["listing_city"].casefold() != expected_city.casefold():
        raise ValueError("Booking city conflicts with message")
    return {column: rows[0][column] for column in columns}


def confirm_fields_with_model(intents: tuple[str, ...], facts: dict) -> None:
    """Fail closed unless OpenRouter selects only available, permitted facts.

    The model gets field names and routine intent only. The response shown to
    the course uses database values assembled by this service.
    """
    fields = list(facts)
    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        json={
            "model": os.environ["OPENROUTER_MODEL"],
            "temperature": 0,
            "max_tokens": 400,
            "provider": {"require_parameters": True},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "booking_fields",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"facts": {"type": "array", "items": {"type": "string", "enum": fields}}},
                        "required": ["facts"],
                        "additionalProperties": False,
                    },
                },
            },
            "messages": [
                {"role": "system", "content": "Return JSON with a facts array of field names. Use every supplied field, and only those fields. Do not invent keys."},
                {"role": "user", "content": json.dumps({"intents": intents, "fields": fields})},
            ],
        },
        timeout=20.0,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("Missing model output")
    if content.strip().startswith("```"):
        content = "\n".join(content.strip().splitlines()[1:-1])
    selected = json.loads(content)["facts"]
    if not isinstance(selected, list) or not all(isinstance(item, str) for item in selected):
        raise ValueError("Invalid model lookup selection")
    if set(selected) != set(facts):
        raise ValueError("Response requested unapproved or incomplete booking fields")


@app.post("/triage", response_model=TriageResult)
def triage(message: TriageRequest) -> TriageResult:
    def escalate(rule: str, reason: str, score: float | None = None):
        return TriageResult(message_id=message.message_id, decision="escalate", reason=reason,
                            matched_rule=rule, danger_score=score)

    intents = classify(message.subject, message.message_body)
    rule_result = decide(intents, message.booking_id)
    try:
        match = detector().match([message.message_body])[0]
    except Exception as error:
        logger.warning("Danger detector failed: %s", type(error).__name__)
        if SAFETY_TYPES.intersection(intents):
            return escalate(f"safety:{intents[0]}", "Send to a human immediately; a safety rule matched.")
        return escalate("detector_unavailable", "Danger detection unavailable; send to a human.")
    score = round(match.score, 6)
    if SAFETY_TYPES.intersection(intents):
        return escalate(f"safety:{intents[0]}", "Send to a human immediately; a safety rule matched.", score)
    if match.score >= DANGER_THRESHOLD:
        return escalate(f"safety:semantic:{match.example_id}", "Send to a human; known danger similarity exceeded threshold.", score)
    if match.score >= DANGER_REVIEW_FLOOR:
        return escalate("safety:uncertain_similarity", "Send to a human; near-threshold danger requires review.", score)
    if rule_result.action == "escalate":
        return escalate(rule_result.reason, "Send to a human for clarification.", score)
    assert message.booking_id is not None
    try:
        fields = tuple(dict.fromkeys(field for intent in intents for field in BOOKING_COLUMNS[intent]))
        facts = read_booking(message.booking_id, fields, message.listing_city)
        confirm_fields_with_model(intents, facts)
    except (httpx.HTTPError, KeyError, ValueError, IndexError, TypeError):
        return escalate("booking_or_reply_unavailable", "Send to a human; unable to verify a booking reply.", score)
    reply = "; ".join(f"{name.replace('_', ' ')}: {value}" for name, value in facts.items())
    return TriageResult(message_id=message.message_id, decision="auto_answer", reason=reply,
                        matched_rule=f"routine:{'+'.join(intents)}", danger_score=score)
