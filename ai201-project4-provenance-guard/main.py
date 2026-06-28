from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from math import sqrt
from time import time
from typing import Any

from flask import Flask, jsonify, request


SUBMISSIONS: dict[str, dict[str, Any]] = {}
APPEALS: dict[str, dict[str, Any]] = {}
AUDIT_LOG: list[dict[str, Any]] = []
CERTIFICATES: dict[str, dict[str, Any]] = {}
RATE_LIMIT_BUCKETS: dict[tuple[str, str, str], list[float]] = {}

RATE_LIMIT_RULES = {
    ("POST", "/submit"): {"limit": 5, "window_seconds": 60},
    ("POST", "/appeal"): {"limit": 3, "window_seconds": 60},
    ("POST", "/certificate"): {"limit": 3, "window_seconds": 60},
    ("GET", "/appeals"): {"limit": 20, "window_seconds": 60},
}

SIGNAL_WEIGHTS = {
    "phrase_repetition": 0.45,
    "rhythm_uniformity": 0.35,
    "specificity_gap": 0.20,
}

AI_MARKER_PHRASES = (
    "it is important to note",
    "in conclusion",
    "overall",
    "furthermore",
    "plays a crucial role",
    "delve into",
    "underscore",
    "not only",
    "but also",
    "as a result",
)

FIRST_PERSON_PRONOUNS = {
    "i",
    "me",
    "my",
    "mine",
    "we",
    "us",
    "our",
    "ours",
}

CONCRETE_DETAIL_WORDS = {
    "afternoon",
    "apartment",
    "brother",
    "bus",
    "car",
    "chair",
    "classroom",
    "coffee",
    "desk",
    "dog",
    "door",
    "draft",
    "elbow",
    "floor",
    "friend",
    "kitchen",
    "lunch",
    "morning",
    "mother",
    "notebook",
    "rain",
    "room",
    "shoes",
    "sidewalk",
    "sister",
    "street",
    "table",
    "teacher",
    "train",
    "window",
    "windows",
}

GENERIC_ABSTRACTION_WORDS = {
    "approach",
    "benefit",
    "clear",
    "consistent",
    "crucial",
    "effective",
    "growth",
    "important",
    "improvement",
    "meaningful",
    "outcome",
    "outcomes",
    "process",
    "progress",
    "result",
    "results",
    "success",
    "support",
    "structured",
    "various",
}

VERIFICATION_METHOD_LABELS = {
    "draft_history": "draft history",
    "platform_account": "platform account",
    "signed_statement": "signed statement",
}


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def attribution_snapshot(submission_id: str) -> dict[str, Any]:
    submission = SUBMISSIONS.get(submission_id)
    if submission is None:
        return {}
    return {
        "labelCode": submission.get("labelCode"),
        "confidence": submission.get("confidence"),
    }


def add_audit_event(
    submission_id: str,
    event_type: str,
    actor: str = "system",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = attribution_snapshot(submission_id)
    event_details = dict(details or {})
    if snapshot:
        event_details.setdefault("labelCode", snapshot["labelCode"])
        event_details.setdefault("confidence", snapshot["confidence"])

    event = {
        "eventId": f"evt_{uuid.uuid4().hex[:12]}",
        "submissionId": submission_id,
        "eventType": event_type,
        "timestamp": now_iso(),
        "actor": actor,
        "labelCode": snapshot.get("labelCode"),
        "confidence": snapshot.get("confidence"),
        "details": event_details,
    }
    AUDIT_LOG.append(event)
    return event


def audit_history(submission_id: str) -> list[dict[str, Any]]:
    return [event for event in AUDIT_LOG if event["submissionId"] == submission_id]


def rate_limit_config() -> dict[str, str]:
    return {
        f"{method} {path}": f"{rule['limit']} per {rule['window_seconds']} seconds"
        for (method, path), rule in RATE_LIMIT_RULES.items()
    }


def client_identifier() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def check_rate_limit() -> tuple[dict[str, Any], int] | None:
    rule = RATE_LIMIT_RULES.get((request.method, request.path))
    if rule is None:
        return None

    current_time = time()
    window_seconds = int(rule["window_seconds"])
    limit = int(rule["limit"])
    bucket_key = (client_identifier(), request.method, request.path)
    recent_hits = [
        hit_time
        for hit_time in RATE_LIMIT_BUCKETS.get(bucket_key, [])
        if current_time - hit_time < window_seconds
    ]

    if len(recent_hits) >= limit:
        retry_after = max(1, int(window_seconds - (current_time - min(recent_hits))))
        RATE_LIMIT_BUCKETS[bucket_key] = recent_hits
        return (
            {
                "error": "Rate limit exceeded.",
                "limit": limit,
                "windowSeconds": window_seconds,
                "retryAfterSeconds": retry_after,
            },
            429,
        )

    recent_hits.append(current_time)
    RATE_LIMIT_BUCKETS[bucket_key] = recent_hits
    return None


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs: list[str] = []

    for block in re.split(r"\n\s*\n+", normalized):
        lines = [" ".join(line.split()) for line in block.split("\n")]
        paragraph = " ".join(line for line in lines if line).strip()
        if paragraph:
            paragraphs.append(paragraph)

    return "\n\n".join(paragraphs)


def tokenize_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", text.lower())


def split_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def coefficient_of_variation(values: list[int], fallback: float = 0.0) -> float:
    if not values:
        return fallback

    mean = sum(values) / len(values)
    if mean == 0:
        return fallback

    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return sqrt(variance) / mean


def repeated_ngram_rate(words: list[str]) -> float:
    total_ngrams = 0
    repeated_ngrams = 0

    for size in (2, 3):
        if len(words) < size:
            continue
        ngrams = [tuple(words[index : index + size]) for index in range(len(words) - size + 1)]
        counts = Counter(ngrams)
        total_ngrams += len(ngrams)
        repeated_ngrams += sum(count - 1 for count in counts.values() if count > 1)

    if total_ngrams == 0:
        return 0.0
    return repeated_ngrams / total_ngrams


def sentence_starter_reuse(sentences: list[str]) -> float:
    starters: list[tuple[str, ...]] = []
    for sentence in sentences:
        words = tokenize_words(sentence)
        if words:
            starters.append(tuple(words[:3]))

    if not starters:
        return 0.0

    most_common_count = Counter(starters).most_common(1)[0][1]
    return most_common_count / len(starters)


def phrase_repetition_reliability(word_count: int) -> float:
    if word_count < 40:
        return 0.35
    if word_count < 120:
        return 0.70
    return 1.00


def score_phrase_repetition(normalized_text: str) -> dict[str, Any]:
    words = tokenize_words(normalized_text)
    word_count = len(words)

    if word_count == 0:
        return {
            "signal": "phrase_repetition",
            "score": 0.5,
            "reliability": 0.1,
            "features": {"word_count": 0},
            "notes": ["Input was too short to score."],
        }

    lowered_text = normalized_text.lower()
    marker_phrase_hits = sum(lowered_text.count(phrase) for phrase in AI_MARKER_PHRASES)
    marker_phrase_rate = (marker_phrase_hits / word_count) * 100
    ngram_rate = repeated_ngram_rate(words)
    sentences = split_sentences(normalized_text)
    starter_reuse = sentence_starter_reuse(sentences)
    type_token_ratio = len(set(words)) / word_count

    marker_score = min(1.0, marker_phrase_rate / 2.5)
    repeat_score = min(1.0, ngram_rate / 0.08)
    starter_score = clamp((starter_reuse - 0.25) / 0.45)
    low_diversity_score = clamp((0.55 - type_token_ratio) / 0.25)

    score = (
        (0.35 * marker_score)
        + (0.25 * repeat_score)
        + (0.25 * starter_score)
        + (0.15 * low_diversity_score)
    )

    return {
        "signal": "phrase_repetition",
        "score": round(clamp(score), 2),
        "reliability": phrase_repetition_reliability(word_count),
        "features": {
            "word_count": word_count,
            "marker_phrase_hits": marker_phrase_hits,
            "marker_phrase_rate": round(marker_phrase_rate, 2),
            "repeated_ngram_rate": round(ngram_rate, 3),
            "sentence_starter_reuse": round(starter_reuse, 2),
            "type_token_ratio": round(type_token_ratio, 2),
        },
        "notes": ["Higher score means more AI-like phrase and repetition patterns."],
    }


def rhythm_uniformity_reliability(sentence_count: int) -> float:
    if sentence_count < 5:
        return 0.30
    if sentence_count < 8:
        return 0.70
    return 1.00


def count_punctuation_types(text: str) -> int:
    punctuation_checks = (
        ".",
        ",",
        ";",
        ":",
        "?",
        "!",
        "-",
        "(",
        ")",
        '"',
        "'",
    )
    return sum(1 for punctuation in punctuation_checks if punctuation in text)


def score_rhythm_uniformity(normalized_text: str) -> dict[str, Any]:
    words = tokenize_words(normalized_text)
    if not words:
        return {
            "signal": "rhythm_uniformity",
            "score": 0.5,
            "reliability": 0.1,
            "features": {
                "sentence_count": 0,
                "mean_sentence_words": 0,
                "sentence_length_cv": 0,
                "paragraph_count": 0,
                "paragraph_length_cv": 0,
                "punctuation_types_used": 0,
                "middle_length_sentence_share": 0,
            },
            "notes": ["Input was too short to score."],
        }

    sentences = split_sentences(normalized_text)
    sentence_word_counts = [len(tokenize_words(sentence)) for sentence in sentences]
    sentence_word_counts = [count for count in sentence_word_counts if count > 0]
    sentence_count = len(sentence_word_counts)

    if sentence_count == 0:
        sentence_word_counts = [len(words)]
        sentence_count = 1

    mean_sentence_words = sum(sentence_word_counts) / sentence_count
    sentence_length_cv = coefficient_of_variation(sentence_word_counts)

    paragraphs = [paragraph for paragraph in normalized_text.split("\n\n") if paragraph.strip()]
    paragraph_word_counts = [len(tokenize_words(paragraph)) for paragraph in paragraphs]
    paragraph_count = len(paragraph_word_counts)
    paragraph_length_cv = (
        coefficient_of_variation(paragraph_word_counts)
        if paragraph_count >= 2
        else 0.5
    )

    punctuation_types_used = count_punctuation_types(normalized_text)
    middle_length_count = sum(1 for count in sentence_word_counts if 12 <= count <= 28)
    middle_length_sentence_share = middle_length_count / sentence_count

    uniform_sentence_score = clamp((0.65 - sentence_length_cv) / 0.45)
    uniform_paragraph_score = clamp((0.70 - paragraph_length_cv) / 0.50)
    low_punctuation_variety_score = clamp((5 - punctuation_types_used) / 5)
    middle_band_score = middle_length_sentence_share

    score = (
        (0.40 * uniform_sentence_score)
        + (0.20 * uniform_paragraph_score)
        + (0.20 * low_punctuation_variety_score)
        + (0.20 * middle_band_score)
    )

    return {
        "signal": "rhythm_uniformity",
        "score": round(clamp(score), 2),
        "reliability": rhythm_uniformity_reliability(sentence_count),
        "features": {
            "sentence_count": sentence_count,
            "mean_sentence_words": round(mean_sentence_words, 1),
            "sentence_length_cv": round(sentence_length_cv, 2),
            "paragraph_count": paragraph_count,
            "paragraph_length_cv": round(paragraph_length_cv, 2),
            "punctuation_types_used": punctuation_types_used,
            "middle_length_sentence_share": round(middle_length_sentence_share, 2),
        },
        "notes": ["Higher score means less burstiness and a more AI-like rhythm."],
    }


def specificity_gap_reliability(word_count: int) -> float:
    if word_count < 40:
        return 0.35
    if word_count < 120:
        return 0.70
    return 1.00


def per_100_words(count: int, word_count: int) -> float:
    if word_count == 0:
        return 0.0
    return (count / word_count) * 100


def score_specificity_gap(normalized_text: str) -> dict[str, Any]:
    words = tokenize_words(normalized_text)
    word_count = len(words)

    if word_count == 0:
        return {
            "signal": "specificity_gap",
            "score": 0.5,
            "reliability": 0.1,
            "features": {
                "word_count": 0,
                "first_person_rate": 0,
                "concrete_detail_rate": 0,
                "numeric_token_rate": 0,
                "generic_abstraction_rate": 0,
            },
            "notes": ["Input was too short to score."],
        }

    first_person_hits = sum(1 for word in words if word in FIRST_PERSON_PRONOUNS)
    concrete_detail_hits = sum(1 for word in words if word in CONCRETE_DETAIL_WORDS)
    numeric_token_hits = sum(1 for word in words if any(character.isdigit() for character in word))
    generic_abstraction_hits = sum(1 for word in words if word in GENERIC_ABSTRACTION_WORDS)

    first_person_rate = per_100_words(first_person_hits, word_count)
    concrete_detail_rate = per_100_words(concrete_detail_hits, word_count)
    numeric_token_rate = per_100_words(numeric_token_hits, word_count)
    generic_abstraction_rate = per_100_words(generic_abstraction_hits, word_count)

    low_detail_score = clamp((2.5 - (concrete_detail_rate + numeric_token_rate)) / 2.5)
    low_personal_score = clamp((1.0 - first_person_rate) / 1.0)
    generic_abstraction_score = min(1.0, generic_abstraction_rate / 4.0)

    score = (
        (0.45 * low_detail_score)
        + (0.25 * low_personal_score)
        + (0.30 * generic_abstraction_score)
    )

    return {
        "signal": "specificity_gap",
        "score": round(clamp(score), 2),
        "reliability": specificity_gap_reliability(word_count),
        "features": {
            "word_count": word_count,
            "first_person_rate": round(first_person_rate, 2),
            "concrete_detail_rate": round(concrete_detail_rate, 2),
            "numeric_token_rate": round(numeric_token_rate, 2),
            "generic_abstraction_rate": round(generic_abstraction_rate, 2),
        },
        "notes": ["Higher score means fewer concrete details and more generic abstraction."],
    }


def combine_confidence(
    signals: dict[str, dict[str, Any]],
    word_count: int,
) -> float:
    denominator = 0.0
    weighted_sum = 0.0

    for signal_name, weight in SIGNAL_WEIGHTS.items():
        signal = signals[signal_name]
        reliability = float(signal["reliability"])
        denominator += weight * reliability
        weighted_sum += weight * float(signal["score"]) * reliability

    if denominator == 0:
        weighted_raw = 0.5
    else:
        weighted_raw = weighted_sum / denominator

    if word_count < 40:
        length_shrink = 0.35
    elif word_count < 120:
        length_shrink = 0.70
    else:
        length_shrink = 1.00

    calibrated = 0.5 + ((weighted_raw - 0.5) * length_shrink)

    signal_scores = [float(signal["score"]) for signal in signals.values()]
    if max(signal_scores) - min(signal_scores) > 0.45:
        calibrated = 0.5 + ((calibrated - 0.5) * 0.80)

    return round(clamp(calibrated), 2)


def choose_label_code(
    confidence: float,
    word_count: int,
    signals: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    signal_scores = [float(signal["score"]) for signal in signals.values()]
    signal_disagreement = max(signal_scores) - min(signal_scores)

    if word_count < 40:
        reasons.append("insufficient_text_length")
    if signal_disagreement > 0.45:
        reasons.append("signal_disagreement")

    if word_count < 40 or signal_disagreement > 0.45:
        label_code = "uncertain"
    elif confidence >= 0.75:
        label_code = "likely_ai"
        reasons.append("strong_ai_patterns")
    elif confidence <= 0.35:
        label_code = "likely_human"
        reasons.append("weak_ai_patterns")
    else:
        label_code = "uncertain"
        reasons.append("mixed_signal_strength")

    if label_code == "uncertain" and not reasons:
        reasons.append("mixed_signal_strength")

    return {"labelCode": label_code, "reasons": reasons}


def compose_label(label_code: str, confidence: float, reasons: list[str] | None = None) -> str:
    ai_confidence_percent = round(confidence * 100)
    human_confidence_percent = round((1 - confidence) * 100)

    if label_code == "likely_ai":
        return (
            "Likely AI-generated or AI-assisted - "
            f"AI-likelihood confidence {ai_confidence_percent}%. "
            "The writing shows repeated AI-like phrasing or unusually even rhythm. "
            "You can appeal this label if you believe it is wrong."
        )

    if label_code == "likely_human":
        return (
            "Likely human-written - "
            f"human-likelihood confidence {human_confidence_percent}%. "
            "The configured detection signals did not find strong AI-generation patterns."
        )

    return (
        "Uncertain provenance - "
        f"AI-likelihood confidence {ai_confidence_percent}%. "
        "The signals are mixed or the text is too short for a reliable label. "
        "This result should not be treated as a final authorship decision."
    )


def find_open_appeal(submission_id: str) -> dict[str, Any] | None:
    for appeal in APPEALS.values():
        if appeal["submissionId"] == submission_id and appeal["appealStatus"] == "open":
            return appeal
    return None


def appeal_queue_row(appeal: dict[str, Any]) -> dict[str, Any]:
    submission = SUBMISSIONS[appeal["submissionId"]]
    text_snippet = submission["text"][:240]

    return {
        "appealId": appeal["appealId"],
        "submissionId": appeal["submissionId"],
        "submittedAt": appeal["submittedAt"],
        "requester": appeal["requester"],
        "currentSubmissionStatus": submission["status"],
        "currentLabelCode": submission["labelCode"],
        "currentLabelText": submission["labelText"],
        "confidence": submission["confidence"],
        "phrase_repetition.score": submission["signals"]["phrase_repetition"]["score"],
        "rhythm_uniformity.score": submission["signals"]["rhythm_uniformity"]["score"],
        "specificity_gap.score": submission["signals"]["specificity_gap"]["score"],
        "textSnippet": text_snippet,
        "reason": appeal["reason"],
        "evidenceSummary": appeal.get("evidenceSummary", ""),
        "auditHistory": audit_history(appeal["submissionId"]),
        "reviewerActions": [
            "uphold_label",
            "change_to_uncertain",
            "change_to_likely_human",
            "change_to_likely_ai",
        ],
        "reviewerNotesField": "",
    }


def submission_response(submission: dict[str, Any]) -> dict[str, Any]:
    response = {
        "submissionId": submission["submissionId"],
        "status": submission["status"],
        "labelCode": submission["labelCode"],
        "labelText": submission["labelText"],
        "confidence": submission["confidence"],
        "confidenceMeaning": submission["confidenceMeaning"],
        "signals": submission["signals"],
        "reasons": submission["reasons"],
    }

    if "appealId" in submission:
        response["appealId"] = submission["appealId"]
        response["appealStatus"] = submission["appealStatus"]

    if "provenanceCertificate" in submission:
        response["provenanceCertificate"] = submission["provenanceCertificate"]

    return response


def compose_certificate_label(verification_method: str) -> str:
    method_label = VERIFICATION_METHOD_LABELS[verification_method]
    return (
        "Verified creator provenance - "
        f"creator supplied {method_label} evidence for this submission. "
        "This verification is separate from the AI-likelihood label."
    )


def build_analytics() -> dict[str, Any]:
    total_submissions = len(SUBMISSIONS)
    label_counts = Counter(submission["labelCode"] for submission in SUBMISSIONS.values())
    appealed_submission_ids = {appeal["submissionId"] for appeal in APPEALS.values()}

    if total_submissions == 0:
        label_ratios = {"likely_ai": 0.0, "likely_human": 0.0, "uncertain": 0.0}
        average_confidence = 0.0
        appeal_rate = 0.0
        certificate_rate = 0.0
    else:
        label_ratios = {
            label_code: round(label_counts.get(label_code, 0) / total_submissions, 2)
            for label_code in ("likely_ai", "likely_human", "uncertain")
        }
        average_confidence = round(
            sum(float(submission["confidence"]) for submission in SUBMISSIONS.values()) / total_submissions,
            2,
        )
        appeal_rate = round(len(appealed_submission_ids) / total_submissions, 2)
        certificate_rate = round(len(CERTIFICATES) / total_submissions, 2)

    return {
        "totalSubmissions": total_submissions,
        "detectionPattern": {
            "counts": {
                "likely_ai": label_counts.get("likely_ai", 0),
                "likely_human": label_counts.get("likely_human", 0),
                "uncertain": label_counts.get("uncertain", 0),
            },
            "ratios": label_ratios,
        },
        "appealRate": appeal_rate,
        "averageConfidence": average_confidence,
        "certificateRate": certificate_rate,
        "openAppeals": sum(1 for appeal in APPEALS.values() if appeal["appealStatus"] == "open"),
        "rateLimits": rate_limit_config(),
    }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.before_request
    def enforce_rate_limits() -> tuple[Any, int] | None:
        rate_limit_response = check_rate_limit()
        if rate_limit_response is None:
            return None

        payload, status_code = rate_limit_response
        return jsonify(payload), status_code

    @app.get("/health")
    def health() -> tuple[Any, int]:
        return jsonify({"status": "ok"}), 200

    @app.post("/submit")
    def submit() -> tuple[Any, int]:
        payload = request.get_json(silent=True) or {}
        text = payload.get("text")

        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Field 'text' is required and must be non-empty."}), 400

        normalized = normalize_text(text)
        phrase_signal = score_phrase_repetition(normalized)
        rhythm_signal = score_rhythm_uniformity(normalized)
        specificity_signal = score_specificity_gap(normalized)
        word_count = int(phrase_signal["features"].get("word_count", 0))
        signals = {
            "phrase_repetition": phrase_signal,
            "rhythm_uniformity": rhythm_signal,
            "specificity_gap": specificity_signal,
        }
        confidence = combine_confidence(signals, word_count)
        label_decision = choose_label_code(confidence, word_count, signals)
        submission_id = f"sub_{uuid.uuid4().hex[:12]}"

        submission = {
            "submissionId": submission_id,
            "createdAt": now_iso(),
            "text": text,
            "normalizedText": normalized,
            "authorId": payload.get("authorId"),
            "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            "status": "labeled",
            "labelCode": label_decision["labelCode"],
            "labelText": compose_label(label_decision["labelCode"], confidence, label_decision["reasons"]),
            "confidence": confidence,
            "confidenceMeaning": "AI-likelihood estimate after calibration",
            "signals": signals,
            "reasons": label_decision["reasons"],
        }
        SUBMISSIONS[submission_id] = submission
        add_audit_event(
            submission_id,
            "submission_labeled",
            details={
                "labelCode": submission["labelCode"],
                "confidence": submission["confidence"],
                "phraseRepetitionScore": phrase_signal["score"],
                "rhythmUniformityScore": rhythm_signal["score"],
                "specificityGapScore": specificity_signal["score"],
                "reasons": submission["reasons"],
            },
        )

        return jsonify(submission_response(submission)), 201

    @app.get("/submission/<submission_id>")
    def get_submission(submission_id: str) -> tuple[Any, int]:
        submission = SUBMISSIONS.get(submission_id)
        if submission is None:
            return jsonify({"error": "Submission not found."}), 404

        response = submission_response(submission)
        response["text"] = submission["text"]
        response["metadata"] = submission["metadata"]
        response["auditHistory"] = audit_history(submission_id)

        open_appeal = find_open_appeal(submission_id)
        if open_appeal is not None:
            response["appeal"] = open_appeal

        return jsonify(response), 200

    @app.post("/appeal")
    def submit_appeal() -> tuple[Any, int]:
        payload = request.get_json(silent=True) or {}
        submission_id = payload.get("submissionId")
        requester = payload.get("requester")
        reason = payload.get("reason")
        requested_label = payload.get("requestedLabel")
        evidence_summary = payload.get("evidenceSummary", "")

        if not isinstance(submission_id, str) or not submission_id.strip():
            return jsonify({"error": "Field 'submissionId' is required."}), 400

        submission = SUBMISSIONS.get(submission_id)
        if submission is None:
            return jsonify({"error": "Submission not found."}), 404

        if not isinstance(requester, str) or not requester.strip():
            return jsonify({"error": "Field 'requester' is required."}), 400

        if not isinstance(reason, str) or not 20 <= len(reason.strip()) <= 1000:
            return jsonify({"error": "Field 'reason' must be 20-1000 characters."}), 400

        allowed_labels = {"likely_human", "uncertain", "likely_ai"}
        if requested_label is not None and requested_label not in allowed_labels:
            return jsonify({"error": "Field 'requestedLabel' must be likely_human, uncertain, or likely_ai."}), 400

        if evidence_summary is not None and not isinstance(evidence_summary, str):
            return jsonify({"error": "Field 'evidenceSummary' must be a string when provided."}), 400

        existing_appeal = find_open_appeal(submission_id)
        if existing_appeal is not None:
            return (
                jsonify(
                    {
                        "appealId": existing_appeal["appealId"],
                        "submissionId": submission_id,
                        "appealStatus": existing_appeal["appealStatus"],
                        "submissionStatus": submission["status"],
                        "message": "An open appeal already exists for this submission.",
                    }
                ),
                200,
            )

        appeal_id = f"app_{uuid.uuid4().hex[:12]}"
        previous_status = submission["status"]
        reason_excerpt = reason.strip()[:240]

        appeal = {
            "appealId": appeal_id,
            "submissionId": submission_id,
            "appealStatus": "open",
            "submittedAt": now_iso(),
            "requester": requester.strip(),
            "reason": reason.strip(),
            "requestedLabel": requested_label,
            "evidenceSummary": evidence_summary.strip() if isinstance(evidence_summary, str) else "",
            "labelAtSubmission": submission["labelCode"],
            "confidenceAtSubmission": submission["confidence"],
            "signalsAtSubmission": submission["signals"],
        }
        APPEALS[appeal_id] = appeal

        submission["status"] = "under_review"
        submission["appealId"] = appeal_id
        submission["appealStatus"] = "open"

        add_audit_event(
            submission_id,
            "appeal_submitted",
            actor=requester.strip(),
            details={
                "appealId": appeal_id,
                "previousLabel": appeal["labelAtSubmission"],
                "previousConfidence": appeal["confidenceAtSubmission"],
                "reasonExcerpt": reason_excerpt,
            },
        )
        add_audit_event(
            submission_id,
            "submission_status_changed",
            actor="system",
            details={"from": previous_status, "to": "under_review", "appealId": appeal_id},
        )

        return (
            jsonify(
                {
                    "appealId": appeal_id,
                    "submissionId": submission_id,
                    "appealStatus": appeal["appealStatus"],
                    "submissionStatus": submission["status"],
                    "message": "Appeal received and marked for human review.",
                }
            ),
            201,
        )

    @app.get("/appeals")
    def list_appeals() -> tuple[Any, int]:
        requested_status = request.args.get("status", "open")
        rows = [
            appeal_queue_row(appeal)
            for appeal in APPEALS.values()
            if requested_status == "all" or appeal["appealStatus"] == requested_status
        ]
        rows.sort(key=lambda row: row["submittedAt"])
        return jsonify({"appeals": rows}), 200

    @app.post("/certificate")
    def create_certificate() -> tuple[Any, int]:
        payload = request.get_json(silent=True) or {}
        submission_id = payload.get("submissionId")
        creator = payload.get("creator")
        verification_method = payload.get("verificationMethod")
        evidence_summary = payload.get("evidenceSummary")

        if not isinstance(submission_id, str) or not submission_id.strip():
            return jsonify({"error": "Field 'submissionId' is required."}), 400

        submission = SUBMISSIONS.get(submission_id)
        if submission is None:
            return jsonify({"error": "Submission not found."}), 404

        if not isinstance(creator, str) or not creator.strip():
            return jsonify({"error": "Field 'creator' is required."}), 400

        if verification_method not in VERIFICATION_METHOD_LABELS:
            return (
                jsonify(
                    {
                        "error": "Field 'verificationMethod' must be draft_history, platform_account, or signed_statement."
                    }
                ),
                400,
            )

        if not isinstance(evidence_summary, str) or len(evidence_summary.strip()) < 20:
            return jsonify({"error": "Field 'evidenceSummary' must be at least 20 characters."}), 400

        existing_certificate = submission.get("provenanceCertificate")
        if existing_certificate is not None:
            return jsonify(existing_certificate), 200

        certificate_id = f"cert_{uuid.uuid4().hex[:12]}"
        certificate = {
            "certificateId": certificate_id,
            "submissionId": submission_id,
            "status": "verified",
            "creator": creator.strip(),
            "verificationMethod": verification_method,
            "verificationLabelText": compose_certificate_label(verification_method),
            "evidenceSummary": evidence_summary.strip(),
            "issuedAt": now_iso(),
        }
        CERTIFICATES[certificate_id] = certificate
        submission["provenanceCertificate"] = certificate

        add_audit_event(
            submission_id,
            "certificate_verified",
            actor=creator.strip(),
            details={
                "certificateId": certificate_id,
                "verificationMethod": verification_method,
                "verificationLabelText": certificate["verificationLabelText"],
            },
        )

        return jsonify(certificate), 201

    @app.get("/analytics")
    def analytics() -> tuple[Any, int]:
        return jsonify(build_analytics()), 200

    @app.get("/audit/<submission_id>")
    def get_audit(submission_id: str) -> tuple[Any, int]:
        if submission_id not in SUBMISSIONS:
            return jsonify({"error": "Submission not found."}), 404
        return jsonify({"submissionId": submission_id, "auditEntries": audit_history(submission_id)}), 200

    return app


app = create_app()


def main() -> None:
    app.run(debug=True)


if __name__ == "__main__":
    main()
