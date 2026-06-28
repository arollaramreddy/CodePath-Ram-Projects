from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import datetime, timezone
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
        submission_id = f"sub_{uuid.uuid4().hex[:12]}"

        submission = {
            "submissionId": submission_id,
            "createdAt": now_iso(),
            "text": text,
            "normalizedText": normalized,
            "authorId": payload.get("authorId"),
            "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            "status": "labeled",
            "labelCode": "uncertain",
            "labelText": "Uncertain provenance - final confidence scoring will be added in M4.",
            "signals": {"phrase_repetition": phrase_signal},
        }
        SUBMISSIONS[submission_id] = submission

        return (
            jsonify(
                {
                    "submissionId": submission_id,
                    "status": submission["status"],
                    "labelCode": submission["labelCode"],
                    "labelText": submission["labelText"],
                    "signals": submission["signals"],
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
