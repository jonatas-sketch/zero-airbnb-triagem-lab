# Guest support triage agent

This classroom prototype prioritizes human review for physical safety and hands off ambiguous requests. Without a recognized intent and a well-formed booking ID, the decision is `escalate`. The live service will separately verify the booking against its read-only source before replying.

| Reviewed type | Decision | Cases | Allowed read-only booking fields keyed by booking_id |
|---|---|---:|---|
| Lockout in progress | escalate | 4 | None |
| Threat or unauthorized presence | escalate | 3 | None |
| Medical injury | escalate | 2 | None |
| Environmental hazard | escalate | 3 | None |
| Unknown or unclear | escalate | 1 | None |
| Refund | auto_answer | 9 | Status, amount, expected date |
| Check-out | auto_answer | 10 | Check-out time, late check-out policy, key return instructions |
| Check-in | auto_answer | 8 | Check-in time, instructions status, entry method |
| Wi-Fi | auto_answer | 7 | Availability, authenticated help reference |
| Refund and check-out | auto_answer | 2 | Combined refund and check-out fields |
| Check-in and Wi-Fi | auto_answer | 1 | Combined check-in and Wi-Fi fields |
| **Total** | **37 auto_answer, 13 escalate** | **50** | |

These 37 outcomes are eligibility for a routine read and reply. The system does not confirm a requested change or reply with a guessed value. Unknown, invalid or conflicting booking data, an uncertain classification, or any safety signal triggers human review. Entry codes, Wi-Fi secrets and booking changes are out of scope. No rule writes booking data.

[Anonymized per-row decisions](examples/sample-outcomes.csv) contain only the exercise message IDs, reviewed types and actions. Raw messages are kept in the local course workspace. The input labels come from reading each message, including the contextual difference between a future worry and a lockout already in progress. The classifier itself is the next stage.

## Reproduce locally

Use Python 3.12 and the course-supplied CSV.

```sh
python -m unittest -v
python examples/label_sample.py /path/to/course-sample.csv
```

## Build prompt and review

Prompt excerpt sent to Claude Code: “Live lockouts, threats, medical and environmental hazards go to a human first, including calm, polite, and non-English messages. Only known routine intents with a verified booking ID may use the minimal allowlisted read-only fields.”

Claude Code hit its account quota. The policy was implemented and tested locally. In review I removed any path for a routine match to override safety, and ruled out reading or returning raw credential fields in this prototype.

## Stage 2: Multilingual danger detection

The [Hugging Face multilingual E5 small model](https://huggingface.co/intfloat/multilingual-e5-small) runs locally with ONNX Runtime. We mean-pool and normalize each sentence embedding and take the maximum cosine similarity across all 40 Trust & Safety examples. Scoring sends no text to Hugging Face. The anchor text and guest messages stay outside the repo.

```
Scored 50 messages against 40 examples at 0.900; flagged 9.
MSG-037,0.905667,true,DEX-01
```

The [50-row score file](examples/danger-scores.csv) includes each source message ID, score, flag and nearest example ID. The threshold is shared in `triage_config.py`. I chose 0.900 on the development sample: it caught the Lisbon lockbox and eight other reviewed risks without rerouting routine requests on score alone. The score is a similarity value, so it is not a probability or a clearance signal.

I reviewed **MSG-037** (0.905667, calm but already locked out), **MSG-050** (0.897320, routine ahead-of-arrival door-code question) and **MSG-012** (0.891835, routine request for instructions). Lowering the threshold further would flag these routine messages. I kept 0.900 and require independent safety handling for low-scoring cases including **MSG-013** (0.868574, Spanish threat), **MSG-029** (0.873060, unauthorized presence), and **MSG-033** (0.879794, Portuguese lockout). The model alone caught 9 of 12 known safety cases in this sample and should never clear any case for auto-answer.

Build prompt excerpt: “Embed every known danger example and all 50 guest messages locally with the same multilingual Hugging Face model. Normalize the vectors, use cosine similarity, and record the highest score and corresponding example for each message. Keep a configurable threshold and audit Lisbon and the borderline cases.” Claude Code was unavailable due to the account quota. The implementation retains the independent safety rules and uses original text rather than topic tags, so a low model score cannot override a safety decision.

```sh
uv run --python 3.12 --with-requirements requirements-danger.txt python examples/score_danger.py /path/to/course-sample.csv /path/to/danger-examples.csv
```
