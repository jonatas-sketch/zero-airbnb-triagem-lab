"""Score each course message without publishing its text."""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from danger import DangerDetector, SentenceEncoder
from triage_config import DANGER_THRESHOLD


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("messages", type=Path)
    parser.add_argument("examples", type=Path)
    args = parser.parse_args()
    with args.messages.open(encoding="utf-8-sig", newline="") as file:
        messages = list(csv.DictReader(file))
    if len(messages) != 50 or len({row["message_id"] for row in messages}) != 50:
        raise ValueError("Expected 50 unique message IDs in the sample")
    detector = DangerDetector.from_course_examples(SentenceEncoder(), args.examples)
    matches = detector.match([row["message_body"] for row in messages])
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["message_id", "danger_score", "danger_flag", "nearest_example_id"])
    for message, match in zip(messages, matches, strict=True):
        flag = match.score >= DANGER_THRESHOLD
        writer.writerow([message["message_id"], f"{match.score:.6f}", str(flag).lower(), match.example_id])
    print(
        f"Scored {len(matches)} messages against {len(detector.ids)} examples at "
        f"{DANGER_THRESHOLD:.3f}; flagged {sum(match.score >= DANGER_THRESHOLD for match in matches)}.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
