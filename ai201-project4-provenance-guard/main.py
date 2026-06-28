from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from math import sqrt
from typing import Any

from flask import Flask, jsonify, request


SUBMISSIONS: dict[str, dict[str, Any]] = {}

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


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def combine_confidence(
    phrase_signal: dict[str, Any],
    rhythm_signal: dict[str, Any],
    word_count: int,
) -> float:
    phrase_reliability = float(phrase_signal["reliability"])
    rhythm_reliability = float(rhythm_signal["reliability"])
    denominator = (0.55 * phrase_reliability) + (0.45 * rhythm_reliability)

    if denominator == 0:
        weighted_raw = 0.5
    else:
        weighted_raw = (
            (0.55 * float(phrase_signal["score"]) * phrase_reliability)
            + (0.45 * float(rhythm_signal["score"]) * rhythm_reliability)
        ) / denominator

    if word_count < 40:
        length_shrink = 0.35
    elif word_count < 120:
        length_shrink = 0.70
    else:
        length_shrink = 1.00

    calibrated = 0.5 + ((weighted_raw - 0.5) * length_shrink)

    if abs(float(phrase_signal["score"]) - float(rhythm_signal["score"])) > 0.40:
        calibrated = 0.5 + ((calibrated - 0.5) * 0.80)

    return round(clamp(calibrated), 2)


def choose_label_code(
    confidence: float,
    word_count: int,
    phrase_signal: dict[str, Any],
    rhythm_signal: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    signal_disagreement = abs(float(phrase_signal["score"]) - float(rhythm_signal["score"]))

    if word_count < 40:
        reasons.append("insufficient_text_length")
    if signal_disagreement > 0.40:
        reasons.append("signal_disagreement")

    if word_count < 40 or signal_disagreement > 0.40:
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


def create_app() -> Flask:
    app = Flask(__name__)

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
        word_count = int(phrase_signal["features"].get("word_count", 0))
        confidence = combine_confidence(phrase_signal, rhythm_signal, word_count)
        label_decision = choose_label_code(confidence, word_count, phrase_signal, rhythm_signal)
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
            "labelText": "Transparency label text will be finalized in M5.",
            "confidence": confidence,
            "confidenceMeaning": "AI-likelihood estimate after calibration",
            "signals": {
                "phrase_repetition": phrase_signal,
                "rhythm_uniformity": rhythm_signal,
            },
            "reasons": label_decision["reasons"],
        }
        SUBMISSIONS[submission_id] = submission

        return (
            jsonify(
                {
                    "submissionId": submission_id,
                    "status": submission["status"],
                    "labelCode": submission["labelCode"],
                    "labelText": submission["labelText"],
                    "confidence": submission["confidence"],
                    "confidenceMeaning": submission["confidenceMeaning"],
                    "signals": submission["signals"],
                    "reasons": submission["reasons"],
                }
            ),
            201,
        )

    return app


app = create_app()


def main() -> None:
    app.run(debug=True)


if __name__ == "__main__":
    main()
