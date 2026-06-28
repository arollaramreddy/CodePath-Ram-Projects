# Provenance Guard

Provenance Guard is a small Flask service that labels submitted text with a transparent provenance estimate: likely AI-generated or AI-assisted, uncertain, or likely human-written. The project is intentionally heuristic and explainable. It is not trying to prove authorship; it is showing how a product could combine multiple signals, represent uncertainty, expose evidence, and provide an appeal path.

The implementation follows the design in `planning.md`.

## What Is Included

- `main.py`: Flask API with submission scoring, transparency labels, appeals, reviewer queue data, and audit logs.
- `planning.md`: implementation spec for signals, uncertainty, labels, appeals, architecture, and AI-tool planning.
- `test_main.py`: unit tests for label reachability, appeal handling, duplicate appeal handling, and audit logging.

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the service:

```bash
python main.py
```

Run tests:

```bash
python -m unittest -v
```

For my local verification, I ran:

```bash
uv run --with flask python -m unittest -v
```

The current test suite has 3 passing tests.

## Architecture

```text
Submission flow

Client
  |
  | POST /submit { text, authorId?, metadata? }
  v
Submit API
  |
  v
Normalizer
  |
  +--> Signal 1: Phrase + Repetition --------+
  |                                          |
  +--> Signal 2: Rhythm + Uniformity --------+--> Confidence Scorer
                                                |
                                                v
                                           Label Composer
                                                |
                                                v
                                           Audit Logger
                                                |
                                                v
                                        Response Builder
                                                |
                                                v
                                             Client

Appeal flow

Client
  |
  | POST /appeal { submissionId, requester, reason, requestedLabel?, evidenceSummary? }
  v
Appeal API
  |
  v
Appeal Processor
  |
  +--> Submission Store: set status = under_review
  |
  +--> Audit Logger: appeal_submitted + submission_status_changed
  |
  v
Response Builder
  |
  v
Client
```

The service stores submissions, appeals, and audit events in in-memory dictionaries/lists. That keeps the project easy to run for the milestone, but it also means data resets when the process restarts. In a real deployment, these stores would move to a database and the appeal queue would become a protected reviewer interface.

## API Surface

- `GET /health`: returns service health.
- `POST /submit`: accepts text, runs both detection signals, returns confidence, label text, and signal evidence.
- `GET /submission/<submissionId>`: returns stored text, current status, label, signal values, appeal state, and audit history.
- `POST /appeal`: opens an appeal for an existing submission and marks it `under_review`.
- `GET /appeals?status=open`: returns reviewer queue rows for open appeals.
- `GET /audit/<submissionId>`: returns audit events for a submission.

## Detection Signals

The system uses two signals that intentionally look for different properties. Both return scores from `0.0` to `1.0`, where `0.0` means more human-like evidence and `1.0` means more AI-like evidence.

### Signal 1: Phrase and Repetition

This signal measures repeated structure, generic AI-associated phrasing, repeated n-grams, reused sentence starters, and low lexical diversity. It looks for phrases such as `it is important to note`, `overall`, `furthermore`, `in conclusion`, `plays a crucial role`, and `as a result`.

Reasoning: this signal is useful because many low-effort AI generations rely on smooth transitions, repeated framing, and generalized language. It is intentionally transparent: the API can show which phrase and repetition features contributed to the score. The tradeoff is that this can over-score some human writing, especially formal essays, corporate writing, or repeated creative forms.

### Signal 2: Rhythm Uniformity

This signal measures sentence-count features, sentence-length variation, paragraph-length variation, punctuation variety, and how often sentences fall into a middle-length band. Higher scores mean the writing is unusually even and less bursty.

Reasoning: human writing often changes pace. A writer may use a fragment, a long sentence, a sudden aside, or uneven punctuation. AI-generated prose often has a steady cadence, especially when asked for polished explanation. This signal catches a different pattern than phrase repetition, so the system is less dependent on a single heuristic.

### What I Would Change For Real Deployment

For production, I would not rely on these heuristics alone. I would collect labeled examples from the actual content domain, evaluate false-positive rates across language backgrounds and writing genres, calibrate scores with held-out data, and add a human review dashboard before any label could affect a person's grade, job, or account. I would also add privacy rules for stored text and avoid exposing raw text to unnecessary systems.

## Confidence Scoring

The returned `confidence` is an AI-likelihood score from `0.0` to `1.0`. A score near `1.0` means the system sees strong AI-like evidence. A score near `0.0` means the system sees weak AI-like evidence. A score around `0.5` means the evidence is mixed or not reliable enough.

The scorer combines the two signal scores with reliability weights:

- Phrase/repetition signal weight: `0.55`
- Rhythm/uniformity signal weight: `0.45`
- Short text shrink: scores for text under 40 words are pulled toward `0.50`
- Medium text shrink: scores for 40-119 words are partially pulled toward `0.50`
- Signal disagreement shrink: if the two signals differ by more than `0.40`, the result is pulled toward `0.50`

I used this scoring approach because the labels should not flip at a naive `0.5` threshold. Short text and conflicting evidence are exactly where the system should become more cautious.

Thresholds:

- `confidence >= 0.75`: `likely_ai`
- `0.36 <= confidence < 0.75`: `uncertain`
- `confidence <= 0.35`: `likely_human`
- Any submission under 40 words is forced to `uncertain`, even if a raw signal is high.

### Example Scores

These are actual outputs from the current implementation.

| Case | Phrase score | Rhythm score | Confidence | Label | Reason |
| --- | ---: | ---: | ---: | --- | --- |
| Repetitive, formulaic AI-like sample | `1.00` | `0.84` | `0.93` | `likely_ai` | `strong_ai_patterns` |
| Concrete, uneven human-like sample | `0.00` | `0.16` | `0.20` | `likely_human` | `weak_ai_patterns` |

The important behavior is that the score changes meaningfully when the evidence changes. The same code path can produce `0.93` for repeated formulaic prose and `0.20` for concrete, varied prose.

## Transparency Labels

The label text is intentionally careful. It does not say the system has proven authorship, and the AI label explicitly mentions appeal rights.

### High-Confidence AI Result

Label code: `likely_ai`

Exact display text:

```text
Likely AI-generated or AI-assisted - AI-likelihood confidence {ai_confidence_percent}%. The writing shows repeated AI-like phrasing or unusually even rhythm. You can appeal this label if you believe it is wrong.
```

Example from testing:

```text
Likely AI-generated or AI-assisted - AI-likelihood confidence 93%. The writing shows repeated AI-like phrasing or unusually even rhythm. You can appeal this label if you believe it is wrong.
```

### High-Confidence Human Result

Label code: `likely_human`

Exact display text:

```text
Likely human-written - human-likelihood confidence {human_confidence_percent}%. The configured detection signals did not find strong AI-generation patterns.
```

Example from testing:

```text
Likely human-written - human-likelihood confidence 80%. The configured detection signals did not find strong AI-generation patterns.
```

### Uncertain Result

Label code: `uncertain`

Exact display text:

```text
Uncertain provenance - AI-likelihood confidence {ai_confidence_percent}%. The signals are mixed or the text is too short for a reliable label. This result should not be treated as a final authorship decision.
```

Example from testing:

```text
Uncertain provenance - AI-likelihood confidence 54%. The signals are mixed or the text is too short for a reliable label. This result should not be treated as a final authorship decision.
```

## Appeal Handling

Any requester with a valid `submissionId` can submit an appeal in the MVP.

Appeal request shape:

```json
{
  "submissionId": "sub_123",
  "requester": "student@example.com",
  "reason": "I wrote this myself and can provide draft history.",
  "requestedLabel": "likely_human",
  "evidenceSummary": "I have revision history and outline notes."
}
```

When an appeal is received, the system:

1. Validates the submission exists.
2. Validates `requester` and a 20-1000 character `reason`.
3. Returns the existing appeal if an open appeal already exists.
4. Creates an `appealId`.
5. Changes the submission status from `labeled` to `under_review`.
6. Stores the appeal with the previous label, confidence, and signal values.
7. Logs `appeal_submitted`.
8. Logs `submission_status_changed`.

Example appeal response from testing:

```json
{
  "appealId": "app_f8fe2ff7a842",
  "appealStatus": "open",
  "message": "Appeal received and marked for human review.",
  "submissionId": "sub_e8d6ca30c890",
  "submissionStatus": "under_review"
}
```

Example audit trail from the same flow:

```text
submission_labeled system {
  "confidence": 0.93,
  "labelCode": "likely_ai",
  "phraseRepetitionScore": 1.0,
  "reasons": ["strong_ai_patterns"],
  "rhythmUniformityScore": 0.84
}

appeal_submitted student@example.com {
  "appealId": "app_f8fe2ff7a842",
  "previousConfidence": 0.93,
  "previousLabel": "likely_ai",
  "reasonExcerpt": "I wrote this myself and can provide draft history."
}

submission_status_changed system {
  "appealId": "app_f8fe2ff7a842",
  "from": "labeled",
  "to": "under_review"
}
```

## Reviewer Queue

`GET /appeals?status=open` returns queue rows with:

- appeal ID and submission ID
- requester and submitted time
- current label and confidence
- phrase and rhythm signal scores
- first 240 characters of the submitted text
- appeal reason and evidence summary
- audit history
- reviewer action names

The MVP does not implement reviewer resolution actions yet. It prepares the queue data needed for that next step.

## Rate-Limit Behavior

The current MVP does not enforce automated rate limits. The API does validate required fields, rejects empty submissions, rejects invalid appeal payloads, and prevents duplicate open appeals for the same submission.

If I were deploying this outside a class project, I would enable per-IP and per-account rate limits, for example:

- `POST /submit`: 30 requests per minute per authenticated user
- `POST /appeal`: 10 requests per hour per requester
- `GET /appeals`: reviewer-only access with authentication

`requirements.txt` already includes `flask-limiter`, so the natural next implementation step would be adding route-level limits and tests for `429` responses.

## Known Limitations

This system will make mistakes because it uses simple visible text heuristics.

Specific likely failure cases:

- A poem with repeated lines and simple vocabulary may score as AI-like because the phrase/repetition signal treats repetition as suspicious, even when repetition is the point of the form.
- A polished corporate memo or college application essay may score as AI-like because it can use smooth transitions, middle-length sentences, and low punctuation variety.
- Writing by an English learner may reuse sentence starters and constrained vocabulary, which can inflate the phrase/repetition score for reasons unrelated to AI.
- Heavily edited AI text with personal details, fragments, and varied punctuation may score as human-like because both signals are based on final surface style, not writing history.
- Very short submissions are not reliable. The implementation forces text under 40 words to `uncertain` because neither signal has enough evidence.

## Spec Reflection

The spec helped most by forcing exact signal outputs, label thresholds, and label text before implementation. Because the spec already said what `phrase_repetition.score`, `rhythm_uniformity.score`, `confidence`, `labelCode`, and `reasons` should look like, the Flask code had a concrete contract to implement instead of a vague "detect AI" goal.

One implementation divergence is that I added `GET /appeals` and `GET /audit/<submissionId>` even though the minimum M5 requirement focused on creating appeals. I added them because they make the reviewer queue and audit trail inspectable during testing and during the portfolio walkthrough. Another practical divergence is persistence: the design names stores and audit logs, but the MVP uses in-memory data structures so the project stays easy to run locally.

## AI Usage

I used an AI coding assistant for planning, implementation, and documentation, but I kept the system behavior tied to the spec and revised places where the output was too vague or mismatched.

Specific instances:

1. I directed the AI to turn the milestone prompt into an implementation-ready `planning.md`. It produced the two-signal design, scoring thresholds, label variants, appeal workflow, and architecture diagram. I revised the spec to make the score direction explicit (`0.0` human-like, `1.0` AI-like), added a short-text uncertainty override, and corrected a sample reliability value so the spec and implementation would agree.

2. I directed the AI to implement M3, M4, and M5 in separate commits. It produced the Flask app skeleton, signal functions, scoring logic, labels, appeal endpoint, audit helpers, and tests. I checked the scores with concrete inputs, kept the conservative thresholds from the spec, and added tests for all three label variants plus duplicate appeal handling.

3. I directed the AI to expand the README into a submission artifact rather than a feature list. It produced the architecture and design-decision sections. I grounded the examples with actual scores from the running code and documented the rate-limit limitation honestly instead of implying production protections that are not implemented yet.

## Portfolio Walkthrough Guide

I cannot record audio or a screen from this repo environment, but this is the short walkthrough script I would use for a 2-3 minute portfolio recording.

### Suggested Recording Flow

1. Show `planning.md` briefly and say: "This project started with a spec that defined the signals, confidence thresholds, label text, and appeal flow before implementation."
2. Show `main.py` and point out `score_phrase_repetition`, `score_rhythm_uniformity`, `combine_confidence`, `compose_label`, and `submit_appeal`.
3. Run the tests:

```bash
python -m unittest -v
```

4. Submit a high-confidence AI-like sample and point out `confidence: 0.93`, `labelCode: likely_ai`, and the two signal scores.
5. Submit a human-like sample and point out `confidence: 0.20`, `labelCode: likely_human`, and the lower signal scores.
6. Submit an appeal for the likely-AI result and show the status changing to `under_review`.
7. Open the audit endpoint and point out the `submission_labeled`, `appeal_submitted`, and `submission_status_changed` events.
8. Close by saying: "The key design decision was not to claim certainty. The project exposes signal evidence, shrinks confidence when evidence is weak, and gives users an appeal path."

### Short Voiceover Draft

```text
This is Provenance Guard, a small Flask service that labels text provenance with transparent uncertainty. I built it from a written spec first, so the implementation had concrete signal outputs, thresholds, label text, and appeal behavior.

The submission endpoint normalizes text, runs two signals, and combines them into an AI-likelihood confidence score. The first signal looks for repeated AI-associated phrasing and repeated structure. The second looks for unusually even rhythm, like low sentence-length variation and limited punctuation variety. I combine them with reliability weights and pull the score toward uncertainty for short text or conflicting signals.

Here is a formulaic repeated sample. It gets a 0.93 confidence and the likely-AI label. Here is a more concrete, uneven personal sample. It gets a 0.20 AI-likelihood score and the likely-human label. A short or mixed sample lands in the uncertain range.

The appeal flow is the accountability layer. When I submit an appeal, the submission moves from labeled to under_review. The system stores the appeal, prevents duplicate open appeals, and writes audit events for the original label and the status change.

If this were production, I would not ship these heuristics as proof. I would calibrate against real domain data, add authentication and rate limiting, persist the audit log, and put a human reviewer in front of high-impact decisions.
```
