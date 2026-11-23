"""Score the actual FastAPI endpoint on the 50-row held-out file."""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from triage_api import app


def score(source: Path):
    with source.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if len(rows) != 50 or len({row["message_id"] for row in rows}) != 50:
        raise ValueError("Expected 50 distinct held-out messages")

    client = TestClient(app)
    fields = ("message_id", "booking_id", "listing_city", "subject", "message_body")
    predictions = []
    for row in rows:
        result = client.post("/triage", json={field: row[field] for field in fields})
        result.raise_for_status()
        decision = result.json()
        decision["category_from_label"] = row["message_class"]
        predictions.append(decision)

    labels_and_decisions = Counter((p["category_from_label"], p["decision"]) for p in predictions)
    missed_safety = labels_and_decisions[("safety", "auto_answer")]
    correct_auto = labels_and_decisions[("routine", "auto_answer")]
    lisbon_message = next(
        (row["message_id"] for row in rows
         if row["listing_city"].casefold() in {"lisbon", "lisboa"}
         and row["message_type"] == "lockout"),
        None,
    )
    example_labels = {
        "MSG-072": "Calm lockout in Lisbon",
        "MSG-056": "Urgent lockout",
        "MSG-070": "Urgent wording, routine check-out",
    }
    examples = [
        {"message_id": row["message_id"], "label": example_labels[row["message_id"]]}
        for row in rows if row["message_id"] in example_labels
    ]
    examples.sort(key=lambda example: list(example_labels).index(example["message_id"]))
    return {
        "examples": examples,
        "spotlight_message_id": lisbon_message,
        "evaluated": len(predictions),
        "safety": labels_and_decisions[("safety", "escalate")] + missed_safety,
        "routine": labels_and_decisions[("routine", "escalate")] + correct_auto,
        "missed_safety_escalations": missed_safety,
        "correct_routine_auto_answers": correct_auto,
        "rubric_passed": missed_safety == 0 and correct_auto >= 30,
        "matched_rules": dict(Counter(p["matched_rule"] for p in predictions)),
        "predictions": predictions,
    }


if __name__ == "__main__":
    results = score(Path(sys.argv[1]))
    print(json.dumps(results, ensure_ascii=False, indent=2))
