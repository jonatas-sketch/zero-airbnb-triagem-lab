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

For the live agent, I added a separate human-review band from 0.890 up to 0.900. A near-threshold score at 0.890 or higher escalates even when the booking looks routine. The danger CSV flag still means the score reached 0.900. MSG-012 and MSG-050 move to human review under this policy. I treat scores below 0.890 only as candidates for the other gates, never as evidence that a message is safe.

## Stage 3: Triage API with Supabase and OpenRouter

The FastAPI `POST /triage` returns exactly `message_id`, `decision`, `reason`, `matched_rule` and `danger_score`. It runs independent safety rules and the multilingual detector before any booking lookup or model call. It hands off danger, near-threshold scores, unknown intent, missing or duplicate bookings, inconsistent listing city, malformed generation and unavailable dependencies. It looks up allowlisted fields by exact `booking_id` through the Supabase Data API. The dedicated reader role can select those fields and cannot mutate the table. Local Supabase holds all 50 booking fixtures with door and Wi-Fi codes excluded. OpenRouter receives only routine intent and permitted field names and produces a structured field selection. The service fills the verified facts from Supabase.

The two supplied development files do not have a verified join. 48 of the 50 guest messages have no matching booking ID, and the two remaining cases contain either duplicate bookings or a conflicting listing city. The routine integration case below is a controlled message created for one unambiguous row in the supplied mock bookings. Both external adapters operated on that case. It is distinct from the original 50 guest rows.

```text
Original course Lisbon message
{"message_id":"MSG-037","decision":"escalate","reason":"Send to a human immediately; a safety rule matched.","matched_rule":"safety:lockout","danger_score":0.905668}

Controlled routine message, genuine lookup in the supplied mock table
{"message_id":"LAB-ROUTINE-01","decision":"auto_answer","reason":"checkout at: 2026-10-24 11:00","matched_rule":"routine:checkout","danger_score":0.839069}
```

The local run also checked conflicting city and missing booking ID return an escalation, and malformed requests get an HTTP 422. The anonymous role could not read the booking table.

Run with Python 3.12, use `supabase/bookings_schema.sql` as a migration in a dedicated local Supabase instance, and load the fixture with `examples/import_bookings.py`. Supply a short-lived reader token, the local Supabase HTTP URL, a free OpenRouter model configured with structured outputs, and the original local danger example path through private environment variables. See `.env.example`.

```sh
uv run --python 3.12 --with-requirements requirements-api.txt uvicorn triage_api:app --host 127.0.0.1 --port 8000
```

Build prompt excerpt: “Build a typed FastAPI POST /triage endpoint. Apply deterministic safety rules and multilingual danger detection before read-only Supabase lookup or OpenRouter generation. Use exact booking IDs, decline missing and duplicate rows, and validate one fixed response shape. Never send guest text, booking IDs, or values to OpenRouter. Verify the Lisbon case and a routine exact-ID fixture with real local Supabase and OpenRouter calls.” Claude Code was unavailable due to the account quota. On review I rejected positional row matching and changed the model interface to accept only preapproved field names, with the final values rendered by the API.

## Held-out evaluation preview

The holdout scorer invokes the FastAPI endpoint on the input fields and adds the course labels only after the decisions return. Use the same private server environment as the API.

```sh
uv run --python 3.12 --with-requirements requirements-api.txt python examples/score_holdout.py /local/path/to/holdout.csv > dashboard/results.json
python -m http.server 58763 --bind 127.0.0.1 --directory dashboard
```

The verified run reached 50 of 50 messages, with 13 safety escalations and zero missed safety escalations. It made 0 of the required 30 correct routine auto-answers. The supplied booking table contains no exact booking IDs for the held-out messages. This read-only preview documents the results and keeps actual booking data local. A passing run and the public dashboard are pending a compatible booking table.
