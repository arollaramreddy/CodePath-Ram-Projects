# Provenance Guard Planning Spec

## Purpose

Provenance Guard labels submitted text with a transparent provenance estimate: likely AI-generated or AI-assisted, uncertain, or likely human-written. This document is the implementation spec for Milestones 3-5 and should be updated before any stretch features are started.

The system will use deterministic heuristic signals for the course project MVP. The score is not proof of authorship; it is a calibrated AI-likelihood estimate based on visible writing patterns.

## Detection Signals

Each detector returns a `SignalResult` object. All signal scores use the same direction: `0.0` means human-like evidence, `1.0` means AI-like evidence.

```json
{
  "signal": "signal_name",
  "score": 0.0,
  "reliability": 1.0,
  "features": {},
  "notes": []
}
```

Implementation guard: empty or whitespace-only submissions should be rejected by `POST /submit` with a `400` response before scoring. If a scoring helper is called directly with no usable words, it should return `score: 0.5`, low reliability, empty features where appropriate, and a note explaining that the input was too short to score.

### Signal 1: AI Phrase and Repetition Score

Function target: `score_phrase_repetition(normalized_text: str) -> dict`

What it measures: repeated structure, generic AI-associated phrasing, low lexical diversity, and repeated sentence openings. This signal is meant to catch polished text that leans on common machine-generated patterns rather than specific human detail.

Raw features:

- `word_count`: number of word tokens after normalization.
- `marker_phrase_hits`: count of configured phrases such as `it is important to note`, `in conclusion`, `overall`, `furthermore`, `plays a crucial role`, `delve into`, `underscore`, `not only`, `but also`, and `as a result`.
- `marker_phrase_rate`: `marker_phrase_hits / word_count * 100`.
- `repeated_ngram_rate`: repeated 2-gram and 3-gram occurrences beyond the first occurrence divided by total 2-grams and 3-grams.
- `sentence_starter_reuse`: share of sentences that use the most common first three-word starter.
- `type_token_ratio`: unique lowercase word tokens divided by total word tokens.

Feature scoring:

- `marker_score = min(1.0, marker_phrase_rate / 2.5)`
- `repeat_score = min(1.0, repeated_ngram_rate / 0.08)`
- `starter_score = clamp((sentence_starter_reuse - 0.25) / 0.45, 0.0, 1.0)`
- `low_diversity_score = clamp((0.55 - type_token_ratio) / 0.25, 0.0, 1.0)`

Signal output:

```json
{
  "signal": "phrase_repetition",
  "score": 0.71,
  "reliability": 1.0,
  "features": {
    "word_count": 184,
    "marker_phrase_hits": 4,
    "marker_phrase_rate": 2.17,
    "repeated_ngram_rate": 0.041,
    "sentence_starter_reuse": 0.38,
    "type_token_ratio": 0.47
  },
  "notes": ["Higher score means more AI-like phrase and repetition patterns."]
}
```

Signal formula:

```text
score =
  0.35 * marker_score +
  0.25 * repeat_score +
  0.25 * starter_score +
  0.15 * low_diversity_score
```

Reliability:

- `0.35` for fewer than 40 words.
- `0.70` for 40-119 words.
- `1.00` for 120 or more words.

### Signal 2: Rhythm Uniformity and Burstiness Score

Function target: `score_rhythm_uniformity(normalized_text: str) -> dict`

What it measures: whether sentence and paragraph rhythm is unusually even. Human writing often has bursts: a short sentence after a long one, uneven punctuation, edits, fragments, or a paragraph that changes pace. AI-generated prose often lands in a narrow band of sentence lengths with balanced punctuation and consistently shaped paragraphs.

Raw features:

- `sentence_count`: number of detected sentences.
- `mean_sentence_words`: average words per sentence.
- `sentence_length_cv`: coefficient of variation for sentence word counts, calculated as standard deviation divided by mean.
- `paragraph_count`: number of non-empty paragraphs.
- `paragraph_length_cv`: coefficient of variation for paragraph word counts, or `0.5` when there are fewer than two paragraphs.
- `punctuation_types_used`: count of punctuation categories present from `.`, `,`, `;`, `:`, `?`, `!`, `-`, parentheses, and quotes.
- `middle_length_sentence_share`: share of sentences between 12 and 28 words.

Feature scoring:

- `uniform_sentence_score = clamp((0.65 - sentence_length_cv) / 0.45, 0.0, 1.0)`
- `uniform_paragraph_score = clamp((0.70 - paragraph_length_cv) / 0.50, 0.0, 1.0)`
- `low_punctuation_variety_score = clamp((5 - punctuation_types_used) / 5, 0.0, 1.0)`
- `middle_band_score = middle_length_sentence_share`

Signal output:

```json
{
  "signal": "rhythm_uniformity",
  "score": 0.64,
  "reliability": 1.0,
  "features": {
    "sentence_count": 9,
    "mean_sentence_words": 18.8,
    "sentence_length_cv": 0.31,
    "paragraph_count": 3,
    "paragraph_length_cv": 0.28,
    "punctuation_types_used": 4,
    "middle_length_sentence_share": 0.78
  },
  "notes": ["Higher score means less burstiness and a more AI-like rhythm."]
}
```

Signal formula:

```text
score =
  0.40 * uniform_sentence_score +
  0.20 * uniform_paragraph_score +
  0.20 * low_punctuation_variety_score +
  0.20 * middle_band_score
```

Reliability:

- `0.30` for fewer than 5 sentences.
- `0.70` for 5-7 sentences.
- `1.00` for 8 or more sentences.

### Combined Confidence Score

The combined `confidence` returned by the API is AI-likelihood in the range `0.0` to `1.0`. It is not displayed as absolute proof; it is the system's calibrated estimate after combining signal evidence and reliability.

Weighted raw score:

```text
weighted_raw =
  ((0.55 * signal_1.score * signal_1.reliability) +
   (0.45 * signal_2.score * signal_2.reliability))
  /
  ((0.55 * signal_1.reliability) +
   (0.45 * signal_2.reliability))
```

Calibration:

```text
length_shrink =
  0.35 when word_count < 40
  0.70 when word_count is 40-119
  1.00 when word_count >= 120

calibrated = 0.5 + ((weighted_raw - 0.5) * length_shrink)

if abs(signal_1.score - signal_2.score) > 0.40:
  calibrated = 0.5 + ((calibrated - 0.5) * 0.80)

confidence = round(clamp(calibrated, 0.0, 1.0), 2)
```

The disagreement rule shrinks the score toward uncertainty when the two signals strongly conflict. For example, if phrasing looks AI-like but rhythm looks human-like, the system should avoid overstating the result.

## Uncertainty Representation

A confidence score of `0.60` means the calibrated signals lean AI-like, but not enough for a likely-AI label. In product terms, `0.60` means "mixed or moderate evidence": the system sees more machine-like evidence than human-like evidence, but the user-facing label remains uncertain.

Label thresholds:

- `confidence >= 0.75`: `likely_ai`
- `0.36 <= confidence < 0.75`: `uncertain`
- `confidence <= 0.35`: `likely_human`

Extra uncertainty rule:

- If `word_count < 40`, force the label to `uncertain` even if the calculated score crosses a threshold. The returned `confidence` should still be included, but the `reasons` array must include `insufficient_text_length`.

API confidence fields:

```json
{
  "confidence": 0.6,
  "confidenceMeaning": "AI-likelihood estimate after calibration",
  "labelCode": "uncertain",
  "reasons": ["mixed_signal_strength"]
}
```

## Transparency Label Design

These are the final label variants for the MVP. The implementation should render the text exactly except for the interpolated percentage values and reason details.

### High-Confidence AI Result

Label code: `likely_ai`

Exact label text:

```text
Likely AI-generated or AI-assisted - AI-likelihood confidence {ai_confidence_percent}%. The writing shows repeated AI-like phrasing or unusually even rhythm. You can appeal this label if you believe it is wrong.
```

Display rule: use when `confidence >= 0.75` and `word_count >= 40`.

### High-Confidence Human Result

Label code: `likely_human`

Exact label text:

```text
Likely human-written - human-likelihood confidence {human_confidence_percent}%. The configured detection signals did not find strong AI-generation patterns.
```

Display rule: use when `confidence <= 0.35` and `word_count >= 40`. `human_confidence_percent = round((1 - confidence) * 100)`.

### Uncertain Result

Label code: `uncertain`

Exact label text:

```text
Uncertain provenance - AI-likelihood confidence {ai_confidence_percent}%. The signals are mixed or the text is too short for a reliable label. This result should not be treated as a final authorship decision.
```

Display rule: use when `0.36 <= confidence < 0.75`, when signal disagreement is high, or when `word_count < 40`.

Label review note: the chosen wording avoids accusing the submitter of misconduct. It names the evidence type, exposes uncertainty, and makes the appeal path visible for the only label that could negatively affect a creator.

## Appeals Workflow

### Who Can Submit an Appeal

For the MVP, any requester who has a valid `submissionId` can submit an appeal. The request must include a requester identifier so the audit log can show who asked for review. In a production version, this should be restricted to the content author, the original submitter, or a reviewer/admin.

### Appeal Request Payload

Endpoint target: `POST /appeal`

```json
{
  "submissionId": "sub_123",
  "requester": "student@example.com",
  "reason": "I wrote this myself and can provide draft history.",
  "requestedLabel": "likely_human",
  "evidenceSummary": "I have Google Docs revision history and outline notes."
}
```

Required fields:

- `submissionId`: must match an existing submission.
- `requester`: non-empty string identifying the person or system submitting the appeal.
- `reason`: 20-1000 characters explaining why the label should be reviewed.

Optional fields:

- `requestedLabel`: one of `likely_human`, `uncertain`, or `likely_ai`.
- `evidenceSummary`: short text description of supporting context. File uploads are out of scope for M5.

### Status Changes and Logging

Submission statuses:

- `labeled`: submission has a current system label and no open appeal.
- `under_review`: an appeal is open and waiting for human review.
- `appeal_upheld`: reviewer kept the original label.
- `appeal_overturned`: reviewer changed the label.

Appeal statuses:

- `open`: received and waiting for review.
- `resolved_upheld`: reviewer kept the original label.
- `resolved_overturned`: reviewer changed the label.
- `rejected`: appeal was invalid, duplicate, or missing required information.

When an appeal is received:

1. Validate that the `submissionId` exists.
2. Validate `requester` and `reason`.
3. If an `open` appeal already exists for the same submission, return the existing appeal instead of creating a duplicate.
4. Create an `appealId`.
5. Set the submission status to `under_review`.
6. Store the appeal payload, the current label, the current confidence, and the current signal outputs.
7. Append an audit event named `appeal_submitted`.
8. Append a second audit event named `submission_status_changed` with `from` and `to` statuses.
9. Return an acknowledgement with the `appealId`, `submissionId`, `appealStatus`, and `submissionStatus`.

Audit event shape:

```json
{
  "eventId": "evt_789",
  "submissionId": "sub_123",
  "eventType": "appeal_submitted",
  "timestamp": "2026-06-28T12:00:00Z",
  "actor": "student@example.com",
  "details": {
    "appealId": "app_456",
    "previousLabel": "likely_ai",
    "previousConfidence": 0.82,
    "reasonExcerpt": "I wrote this myself and can provide draft history."
  }
}
```

### Human Reviewer Queue

A reviewer opening the appeal queue should see one row per open appeal, sorted oldest first:

- `appealId`
- `submissionId`
- `submittedAt`
- `requester`
- `currentSubmissionStatus`
- `currentLabelCode`
- `currentLabelText`
- `confidence`
- `phrase_repetition.score`
- `rhythm_uniformity.score`
- first 240 characters of submitted text
- appeal reason
- evidence summary
- audit history link or embedded event list
- reviewer actions: `uphold_label`, `change_to_uncertain`, `change_to_likely_human`, `change_to_likely_ai`
- reviewer notes field

M5 only needs to create the appeal and expose enough stored data to support this queue later. Full reviewer resolution actions can be stretch work.

## Anticipated Edge Cases

The MVP will handle some content poorly. These cases should be documented in the API response `reasons` or reviewer notes when detected.

1. A poem with repeated lines, simple vocabulary, and deliberate parallel structure may score AI-like on repetition even when it is clearly human creative writing.
2. A polished college application essay or corporate memo may have smooth sentence lengths, transition phrases, and low punctuation variety, causing both signals to lean AI-like.
3. A short answer under 40 words does not contain enough evidence for stable scoring, so the system must force the uncertain label.
4. AI-generated text that has been heavily edited with personal anecdotes, fragments, typos, and varied punctuation may score human-like despite synthetic origin.
5. Writing by an English learner may use repeated sentence starters and constrained vocabulary, which can inflate the phrase and repetition score.

## API Surface

### POST /submit

Request:

```json
{
  "text": "Required submitted text.",
  "authorId": "optional-author-id",
  "metadata": {
    "source": "optional source context"
  }
}
```

Response:

```json
{
  "submissionId": "sub_123",
  "status": "labeled",
  "labelCode": "uncertain",
  "labelText": "Uncertain provenance - AI-likelihood confidence 60%. The signals are mixed or the text is too short for a reliable label. This result should not be treated as a final authorship decision.",
  "confidence": 0.6,
  "confidenceMeaning": "AI-likelihood estimate after calibration",
  "signals": {
    "phrase_repetition": {},
    "rhythm_uniformity": {}
  },
  "reasons": ["mixed_signal_strength"]
}
```

### POST /appeal

Request and response follow the appeal workflow above.

### GET /submission/{submissionId}

Returns the stored submission, current label, confidence, signal values, status, and appeal status if one exists.

### GET /health

Returns:

```json
{
  "status": "ok"
}
```

## Architecture

Milestone 1 reference diagram:

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
  +--> Signal 2: Rhythm + Burstiness --------+--> Confidence Scorer
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


Reviewer flow, stretch-ready

Reviewer
  |
  | GET /appeals?status=open
  v
Appeal Queue
  |
  +--> Submission text snippet
  +--> Current label + confidence
  +--> Signal details
  +--> Appeal reason + evidence summary
  +--> Audit history
```

Submission flow narrative: a client submits text to `POST /submit`, the service normalizes it, runs both heuristic signals, calibrates them into one AI-likelihood confidence score, composes a transparent label, logs the decision, and returns the label plus signal details. Appeal flow narrative: a client submits `POST /appeal` with a valid submission ID and reason, the system marks the submission `under_review`, stores the appeal, logs the status change, and returns an acknowledgement. Reviewer queue support comes from the stored submission, signal, label, appeal, and audit records.

## AI Tool Plan

### M3: Submission Endpoint and First Signal

Spec sections to provide to the AI tool:

- `Detection Signals`, especially `Signal 1: AI Phrase and Repetition Score`
- `API Surface`, especially `POST /submit`
- `Architecture`

Ask the AI tool to generate:

- Flask app skeleton with `POST /submit` and `GET /health`.
- `normalize_text(text)` helper.
- `score_phrase_repetition(normalized_text)` exactly following the feature names and formula in this spec.
- In-memory submission storage keyed by generated `submissionId`.
- Temporary M3 response that includes the first signal output and a placeholder label of `uncertain` until M4 scoring is implemented.

Verification before endpoint wiring:

- Call `normalize_text` directly with text containing extra spaces, newlines, and mixed punctuation.
- Call `score_phrase_repetition` directly with a generic AI-like paragraph using phrases such as `it is important to note`, `furthermore`, and `in conclusion`; expect a higher score.
- Call `score_phrase_repetition` directly with a specific human-like paragraph containing concrete details, varied wording, and few repeated phrases; expect a lower score.
- Confirm the direct function output includes `signal`, `score`, `reliability`, `features`, and `notes`.
- After wiring, send `POST /submit` and confirm the response includes `submissionId`, `status`, `signals.phrase_repetition`, and stored submission data.

### M4: Second Signal and Confidence Scoring

Spec sections to provide to the AI tool:

- `Detection Signals`
- `Combined Confidence Score`
- `Uncertainty Representation`
- `Architecture`

Ask the AI tool to generate:

- `score_rhythm_uniformity(normalized_text)` exactly following the feature names and formula in this spec.
- `combine_confidence(signal_1, signal_2, word_count)` using weighted reliability, length shrink, disagreement shrink, clamping, and rounding.
- `choose_label_code(confidence, word_count, signal_1, signal_2)` using the three threshold ranges and the short-text uncertainty override.
- Updated `POST /submit` response with both signal outputs, `confidence`, `labelCode`, and `reasons`.

Verification:

- Test clearly AI-like text with generic transitions, repeated phrasing, and even sentence lengths; expect confidence to move toward `likely_ai`.
- Test clearly human-like text with concrete personal detail, uneven sentence lengths, and varied punctuation; expect confidence to move toward `likely_human`.
- Test a short text under 40 words; expect `labelCode` to be `uncertain` even if a raw signal score is high.
- Test a disagreement case where phrase repetition is high but rhythm variation is high; expect confidence to shrink toward `0.50`.
- Confirm scores vary meaningfully rather than clustering around one value.

### M5: Production Layer, Labels, and Appeals

Spec sections to provide to the AI tool:

- `Transparency Label Design`
- `Appeals Workflow`
- `API Surface`
- `Architecture`

Ask the AI tool to generate:

- `compose_label(label_code, confidence, reasons)` using the exact three label text variants.
- Final `POST /submit` response that includes `labelText`, `confidenceMeaning`, and `reasons`.
- `POST /appeal` endpoint with validation, duplicate-open-appeal handling, submission status updates, appeal storage, and audit logging.
- `GET /submission/{submissionId}` to inspect current status, label, confidence, signals, and appeal state.
- Basic in-memory audit log helpers for submission and appeal events.

Verification:

- Use targeted test inputs or direct function calls to make all three label variants reachable: `likely_ai`, `likely_human`, and `uncertain`.
- Confirm the high-confidence human label displays human-likelihood confidence as `1 - confidence`.
- Submit an appeal for a likely-AI submission and confirm the submission status changes from `labeled` to `under_review`.
- Submit a duplicate appeal for the same submission and confirm it returns the existing open appeal instead of creating another.
- Inspect the stored audit events and confirm both `appeal_submitted` and `submission_status_changed` were recorded.

## Stretch Feature Rule

Before starting any stretch feature, update this file with the feature's scope, new API contract, changes to scoring or labels, and verification plan. Stretch work must not silently change the confidence meaning, label thresholds, or appeal statuses defined above.

## Stretch Feature Plan

This section was added before implementing stretch features.

### Stretch 1: Ensemble Detection

Scope: add a third signal named `specificity_gap` and update the scorer from a two-signal weighted score to a three-signal ensemble. The score direction remains unchanged: `0.0` is human-like evidence and `1.0` is AI-like evidence.

What the third signal measures: whether the text lacks concrete, personal, sensory, or verifiable details while leaning on abstract general-purpose language. It should capture a different property than phrase repetition and rhythm uniformity. A paragraph can have no AI marker phrases and still feel generic; this signal catches that genericness.

Signal output:

```json
{
  "signal": "specificity_gap",
  "score": 0.72,
  "reliability": 1.0,
  "features": {
    "word_count": 160,
    "first_person_rate": 0.0,
    "concrete_detail_rate": 0.6,
    "numeric_token_rate": 0.0,
    "generic_abstraction_rate": 4.4
  },
  "notes": ["Higher score means fewer concrete details and more generic abstraction."]
}
```

Ensemble weighting:

- `phrase_repetition`: `0.45`
- `rhythm_uniformity`: `0.35`
- `specificity_gap`: `0.20`

Conflict handling: if the highest signal score and lowest signal score differ by more than `0.45`, shrink the final confidence toward `0.50`. The label thresholds remain unchanged.

Verification: submit a formulaic, generic sample and confirm all three signal scores are visible alongside the combined score. Submit a concrete personal sample and confirm the specificity score moves lower than the generic sample.

### Stretch 2: Provenance Certificate

Scope: add `POST /certificate` so a creator can complete a lightweight verification step for an existing submission. This is separate from AI detection. A certificate does not erase the AI-likelihood label; it adds a distinct verified provenance label.

Verification step: the requester provides `submissionId`, `creator`, `verificationMethod`, and `evidenceSummary`. Accepted MVP verification methods are `draft_history`, `platform_account`, and `signed_statement`. The `evidenceSummary` must be at least 20 characters.

Verified label text:

```text
Verified creator provenance - creator supplied {verification_method_label} evidence for this submission. This verification is separate from the AI-likelihood label.
```

Status and logging: a successful certificate creates `certificateId`, stores it on the submission, and appends a `certificate_verified` audit event with the current attribution result and confidence.

Verification: create a submission, call `POST /certificate`, then call `GET /submission/{submissionId}` and confirm the certificate label appears separately from the standard transparency label.

### Stretch 3: Analytics Dashboard Endpoint

Scope: add `GET /analytics` returning dashboard-ready JSON. This counts as a source-visible dashboard view for the MVP.

Metrics:

- detection pattern: counts and ratios for `likely_ai`, `likely_human`, and `uncertain`
- appeal rate: appealed submissions divided by total submissions
- average confidence
- certificate rate
- rate limit configuration

Verification: create at least three submissions across label types, submit one appeal, verify one certificate, and confirm `/analytics` returns all metrics.

### Rate Limiting and Audit Hardening

Scope: add route-level in-memory rate limiting with clear `429` JSON responses. Chosen demo-friendly limits:

- `POST /submit`: 5 per minute per client
- `POST /appeal`: 3 per minute per client
- `POST /certificate`: 3 per minute per client
- `GET /appeals`: 20 per minute per client

Reasoning: content submission is the highest-volume action, appeals and certificates are lower-volume trust actions, and reviewer queues need enough headroom for normal refreshes.

Audit hardening: every audit event should include a timestamp, event type, actor, `labelCode`, and `confidence` when the submission exists. This makes the log satisfy the rubric even for status-change events.
