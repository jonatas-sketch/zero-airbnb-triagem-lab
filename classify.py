"""Context rules that run before embeddings, lookup, and model generation."""

import re
import unicodedata

SAFETY_RULES = {
    "hazard": (
        r"\bgas leak\b|\b(?:gas|stove|oven|socket|outlet)\b.{0,32}\b(?:smell|smells|sparks|burning)\b",
        r"\b(?:smell|smells|odor|odour|cheiro|olor)\b.{0,40}\b(?:gas|burning|smoke|socket|outlet|gasolina)\b",
        r"\b(?:burning smell|smoke alarm|carbon monoxide|fogo|fuma[cç]a|olor a gas|humo|odeur de gaz)\b",
    ),
    "medical": (
        r"\b(?:bleeding|cannot breathe|can't breathe|unconscious|seizure|convulsi[oó]n|sangrando)\b",
        r"\b(?:fell|slipped|hit|ca[ií]u|cay[oó])\b.{0,90}\b(?:bleed|bleeding|swelling|dizzy|hurts|broken|head|wrist|ankle|sangue|mareado)\b",
        r"\b(?:chest pain|head injury|severe allergic reaction|dolor de pecho|dor no peito)\b",
    ),
    "threat": (
        r"\b(?:blocking|blocked)\b.{0,25}\b(?:exit|door|way out)\b",
        r"\b(?:pounding|banging|golpeando|batendo)\b.{0,38}\b(?:door|puerta|porta)\b.{0,75}\b(?:yelling|screaming|open|gritando|abrir|abramos)\b",
        r"\b(?:won't leave|refuses to leave|(?:will|he'll|she'll|they'll) stay the night|let himself in|forcing the door|amea[cç]a|me amenaza|creíble amenaza)\b",
        r"\b(?:threatened to hurt|actual robbery|assaulted|me agredi[oó]|me atac[oó])\b",
    ),
    "lockout": (
        r"\b(?:we are|we're|i am|i'm|currently|now|still) (?:still |currently )?locked out\b|^locked out\b",
        r"\b(?:trancad[oa]s? fora|encerrad[oa]s? fuera|hors de l.appartement)\b",
        r"\b(?:lockbox|keypad|code|door|key|c[oó]digo|porta|puerta)\b.{0,36}\b(?:won't|doesn't|does not|can't|cannot|failed|is wrong|isn't working|n[aã]o abre|no abre|no funciona)\b",
        r"\b(?:stand(?:ing)? outside|locked out|stranded)\b.{0,65}\b(?:host|night|cold|rain|street|children|kids)\b",
    ),
}
ROUTINE_CUES = {
    "refund": r"refund|reembolso|remboursement|r[uü]ckerstattung|overcharg|double charge|charged twice|duplicate.{0,16}fee",
    "checkout": r"check[ -]?out|leaving time|where.{0,20}keys go|key return",
    "checkin": r"check[ -]?in|door code|lockbox code|keypad code|key safe code|entry code|schl[uü]sselbox|c[oó]digo.{0,20}(?:entrada|porta)",
    "wifi": r"wi[ -]?fi|internet|router|network password|mot de passe",
}


def classify(subject: str, body: str) -> tuple[str, ...]:
    text = unicodedata.normalize("NFKC", f"{subject}. {body}")
    text = re.sub(r"[’‘]", "'", text).casefold().strip(". ")
    for intent, patterns in SAFETY_RULES.items():
        if any(re.search(pattern, text) for pattern in patterns):
            return (intent,)
    return tuple(intent for intent, pattern in ROUTINE_CUES.items() if re.search(pattern, text))
