"""Compute anonymized routing outcomes for all 50 course rows."""
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rules import decide


# Manual intent review of the supplied sample, independent of the policy under test.
TYPES = (
    "refund checkout wifi lockout checkin refund checkout wifi hazard refund+checkout "
    "checkout checkin threat refund wifi checkin medical checkout wifi refund "
    "hazard checkout checkin refund hazard checkin+wifi checkout refund threat wifi "
    "checkout refund+checkout lockout wifi checkin refund lockout checkout checkin refund "
    "medical checkin checkout threat wifi checkout unknown lockout refund checkin"
).split()


def score_sample(source):
    with open(source, encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    ids = [f"MSG-{row_number:03d}" for row_number in range(1, 51)]
    if [row["message_id"] for row in rows] != ids or len(TYPES) != len(ids):
        raise ValueError("Expected the original ordered 50-message course exercise")
    counts = Counter()
    print("message_id,reviewed_types,decision,reason")
    for row, label in zip(rows, TYPES, strict=True):
        intents = tuple(label.split("+"))
        decision = decide(intents, row["booking_id"])
        counts[(label, decision.action)] += 1
        print(f"{row['message_id']},{label},{decision.action},{decision.reason}")
    print(counts, file=sys.stderr)


if __name__ == "__main__":
    score_sample(sys.argv[1])
