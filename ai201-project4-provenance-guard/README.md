# Provenance Guard

Provenance Guard is a small Flask service that labels submitted text with a transparent provenance estimate: likely AI-generated or AI-assisted, uncertain, or likely human-written. The project is intentionally heuristic and explainable. It is not trying to prove authorship; it is showing how a product could combine multiple signals, represent uncertainty, expose evidence, and provide an appeal path.

The implementation follows the design in `planning.md`.

## What Is Included

- `main.py`: Flask API with submission scoring, transparency labels, appeals, reviewer queue data, and audit logs.
- `planning.md`: implementation spec for signals, uncertainty, labels, appeals, architecture, and AI-tool planning.
- `test_main.py`: unit tests for label reachability, appeal handling, duplicate appeal handling, rate limiting, provenance certificates, analytics, and audit logging.

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

The current test suite has 6 passing tests.

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

Stretch flows

POST /certificate
  |
  +--> Verify creator evidence
  +--> Store provenance certificate
  +--> Add certificate_verified audit event

GET /analytics
  |
  +--> Detection pattern metrics
  +--> Appeal rate
  +--> Average confidence
  +--> Certificate rate
```

The service stores submissions, appeals, and audit events in in-memory dictionaries/lists. That keeps the project easy to run for the milestone, but it also means data resets when the process restarts. In a real deployment, these stores would move to a database and the appeal queue would become a protected reviewer interface.

## API Surface

- `GET /health`: returns service health.
- `POST /submit`: accepts text, runs both detection signals, returns confidence, label text, and signal evidence.
- `GET /submission/<submissionId>`: returns stored text, current status, label, signal values, appeal state, and audit history.
- `POST /appeal`: opens an appeal for an existing submission and marks it `under_review`.
- `GET /appeals?status=open`: returns reviewer queue rows for open appeals.
- `GET /audit/<submissionId>`: returns audit events for a submission.
- `POST /certificate`: verifies creator-provided provenance evidence and adds a distinct verified provenance label.
- `GET /analytics`: returns dashboard-ready metrics for detection pattern, appeal rate, average confidence, certificate rate, and rate limits.

## Detection Signals

The system uses three signals that intentionally look for different properties. Each signal returns a score from `0.0` to `1.0`, where `0.0` means more human-like evidence and `1.0` means more AI-like evidence.

### Signal 1: Phrase and Repetition

This signal measures repeated structure, generic AI-associated phrasing, repeated n-grams, reused sentence starters, and low lexical diversity. It looks for phrases such as `it is important to note`, `overall`, `furthermore`, `in conclusion`, `plays a crucial role`, and `as a result`.

Reasoning: this signal is useful because many low-effort AI generations rely on smooth transitions, repeated framing, and generalized language. It is intentionally transparent: the API can show which phrase and repetition features contributed to the score. The tradeoff is that this can over-score some human writing, especially formal essays, corporate writing, or repeated creative forms.

### Signal 2: Rhythm Uniformity

This signal measures sentence-count features, sentence-length variation, paragraph-length variation, punctuation variety, and how often sentences fall into a middle-length band. Higher scores mean the writing is unusually even and less bursty.

Reasoning: human writing often changes pace. A writer may use a fragment, a long sentence, a sudden aside, or uneven punctuation. AI-generated prose often has a steady cadence, especially when asked for polished explanation. This signal catches a different pattern than phrase repetition, so the system is less dependent on a single heuristic.

### Signal 3: Specificity Gap

This signal measures whether the text lacks concrete, personal, sensory, or verifiable details while leaning on abstract language. It checks first-person references, concrete detail words, numeric tokens, and generic abstraction words such as `process`, `growth`, `outcomes`, `effective`, and `important`.

Reasoning: some AI-like text is not repetitive enough to trigger the first signal and not uniform enough to trigger the rhythm signal, but it still stays generic. The specificity gap signal gives the ensemble a way to notice missing concrete anchors. What it misses: a human can intentionally write abstractly, and AI text can include fake personal details, so this signal is useful but not proof.

### What I Would Change For Real Deployment

For production, I would not rely on these heuristics alone. I would collect labeled examples from the actual content domain, evaluate false-positive rates across language backgrounds and writing genres, calibrate scores with held-out data, and add a human review dashboard before any label could affect a person's grade, job, or account. I would also add privacy rules for stored text and avoid exposing raw text to unnecessary systems.

## Confidence Scoring

The returned `confidence` is an AI-likelihood score from `0.0` to `1.0`. A score near `1.0` means the system sees strong AI-like evidence. A score near `0.0` means the system sees weak AI-like evidence. A score around `0.5` means the evidence is mixed or not reliable enough.

The scorer combines the three signal scores with reliability weights:

- Phrase/repetition signal weight: `0.45`
- Rhythm/uniformity signal weight: `0.35`
- Specificity-gap signal weight: `0.20`
- Short text shrink: scores for text under 40 words are pulled toward `0.50`
- Medium text shrink: scores for 40-119 words are partially pulled toward `0.50`
- Signal disagreement shrink: if the highest and lowest signal scores differ by more than `0.45`, the result is pulled toward `0.50`

I used this scoring approach because the labels should not flip at a naive `0.5` threshold. Short text and conflicting evidence are exactly where the system should become more cautious.

Thresholds:

- `confidence >= 0.75`: `likely_ai`
- `0.36 <= confidence < 0.75`: `uncertain`
- `confidence <= 0.35`: `likely_human`
- Any submission under 40 words is forced to `uncertain`, even if a raw signal is high.

### Example Scores

These are actual outputs from the current implementation.

| Case | Phrase score | Rhythm score | Specificity score | Confidence | Label | Reason |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Repetitive, formulaic AI-like sample | `1.00` | `0.84` | `1.00` | `0.94` | `likely_ai` | `strong_ai_patterns` |
| Concrete, uneven human-like sample | `0.00` | `0.16` | `0.00` | `0.19` | `likely_human` | `weak_ai_patterns` |

The important behavior is that the score changes meaningfully when the evidence changes. The same code path can produce `0.94` for repeated formulaic prose and `0.19` for concrete, varied prose.

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
Likely AI-generated or AI-assisted - AI-likelihood confidence 94%. The writing shows repeated AI-like phrasing or unusually even rhythm. You can appeal this label if you believe it is wrong.
```

### High-Confidence Human Result

Label code: `likely_human`

Exact display text:

```text
Likely human-written - human-likelihood confidence {human_confidence_percent}%. The configured detection signals did not find strong AI-generation patterns.
```

Example from testing:

```text
Likely human-written - human-likelihood confidence 81%. The configured detection signals did not find strong AI-generation patterns.
```

### Uncertain Result

Label code: `uncertain`

Exact display text:

```text
Uncertain provenance - AI-likelihood confidence {ai_confidence_percent}%. The signals are mixed or the text is too short for a reliable label. This result should not be treated as a final authorship decision.
```

Example from testing:

```text
Uncertain provenance - AI-likelihood confidence 55%. The signals are mixed or the text is too short for a reliable label. This result should not be treated as a final authorship decision.
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
  "appealId": "app_2f506b3fe83c",
  "appealStatus": "open",
  "message": "Appeal received and marked for human review.",
  "submissionId": "sub_1b82e6edafd4",
  "submissionStatus": "under_review"
}
```

Example audit trail from the same flow:

```text
submission_labeled likely_ai 0.94 2026-06-28T22:10:59.530163Z {
  "confidence": 0.94,
  "labelCode": "likely_ai",
  "phraseRepetitionScore": 1.0,
  "reasons": ["strong_ai_patterns"],
  "rhythmUniformityScore": 0.84,
  "specificityGapScore": 1.0
}

appeal_submitted likely_ai 0.94 2026-06-28T22:10:59.530866Z {
  "appealId": "app_2f506b3fe83c",
  "confidence": 0.94,
  "labelCode": "likely_ai",
  "previousConfidence": 0.94,
  "previousLabel": "likely_ai",
  "reasonExcerpt": "I wrote this myself and can provide draft history."
}

submission_status_changed likely_ai 0.94 2026-06-28T22:10:59.530870Z {
  "appealId": "app_2f506b3fe83c",
  "confidence": 0.94,
  "from": "labeled",
  "labelCode": "likely_ai",
  "to": "under_review"
}
```

## Reviewer Queue

`GET /appeals?status=open` returns queue rows with:

- appeal ID and submission ID
- requester and submitted time
- current label and confidence
- phrase, rhythm, and specificity signal scores
- first 240 characters of the submitted text
- appeal reason and evidence summary
- audit history
- reviewer action names

The MVP does not implement reviewer resolution actions yet. It prepares the queue data needed for that next step.

## Rate-Limit Behavior

The current MVP enforces in-memory route-level limits. The limits are intentionally low enough to demonstrate during grading, but still tied to realistic writing-platform behavior.

- `POST /submit`: 5 requests per 60 seconds per client. Submissions are the highest-volume action, so this gets the largest trust-action limit in the demo.
- `POST /appeal`: 3 requests per 60 seconds per client. Appeals should be thoughtful and lower-volume than submissions.
- `POST /certificate`: 3 requests per 60 seconds per client. Verification is also a low-volume trust action.
- `GET /appeals`: 20 requests per 60 seconds per client. Reviewers may refresh the queue, so this is higher than appeal creation.

Demo behavior from testing `POST /submit` six times in one window:

```text
rate 1 201
rate 2 201
rate 3 201
rate 4 201
rate 5 201
rate 6 429 Rate limit exceeded.
```

The `429` response is structured JSON:

```json
{
  "error": "Rate limit exceeded.",
  "limit": 5,
  "windowSeconds": 60,
  "retryAfterSeconds": 60
}
```

For production, I would move rate-limit state out of memory and into Redis or another shared store so limits work across multiple server processes.

## Provenance Certificate

The provenance certificate stretch feature is separate from AI detection. A creator can complete a lightweight verification step for an existing submission by sending `submissionId`, `creator`, `verificationMethod`, and `evidenceSummary` to `POST /certificate`.

Accepted verification methods:

- `draft_history`
- `platform_account`
- `signed_statement`

Verified certificate label:

```text
Verified creator provenance - creator supplied {verification_method_label} evidence for this submission. This verification is separate from the AI-likelihood label.
```

Example certificate response:

```json
{
  "certificateId": "cert_e7d85a078b6f",
  "creator": "student@example.com",
  "evidenceSummary": "I can provide timestamped draft history for this text.",
  "issuedAt": "2026-06-28T22:10:59.530984Z",
  "status": "verified",
  "submissionId": "sub_1b82e6edafd4",
  "verificationLabelText": "Verified creator provenance - creator supplied draft history evidence for this submission. This verification is separate from the AI-likelihood label.",
  "verificationMethod": "draft_history"
}
```

This verified label appears under `provenanceCertificate` in `GET /submission/<submissionId>`, so it is distinguishable from the standard `labelText`.

## Analytics Dashboard Endpoint

`GET /analytics` returns a dashboard-ready JSON view with at least three metrics:

- detection pattern: counts and ratios for `likely_ai`, `likely_human`, and `uncertain`
- appeal rate
- average confidence
- certificate rate
- open appeals
- active rate-limit configuration

Example analytics response:

```json
{
  "appealRate": 0.33,
  "averageConfidence": 0.56,
  "certificateRate": 0.33,
  "detectionPattern": {
    "counts": {
      "likely_ai": 1,
      "likely_human": 1,
      "uncertain": 1
    },
    "ratios": {
      "likely_ai": 0.33,
      "likely_human": 0.33,
      "uncertain": 0.33
    }
  },
  "openAppeals": 1,
  "rateLimits": {
    "GET /appeals": "20 per 60 seconds",
    "POST /appeal": "3 per 60 seconds",
    "POST /certificate": "3 per 60 seconds",
    "POST /submit": "5 per 60 seconds"
  },
  "totalSubmissions": 3
}
```

## Known Limitations

This system will make mistakes because it uses simple visible text heuristics.

Specific likely failure cases:

- A poem with repeated lines and simple vocabulary may score as AI-like because the phrase/repetition signal treats repetition as suspicious, even when repetition is the point of the form.
- A polished corporate memo or college application essay may score as AI-like because it can use smooth transitions, middle-length sentences, and low punctuation variety.
- Writing by an English learner may reuse sentence starters and constrained vocabulary, which can inflate the phrase/repetition score for reasons unrelated to AI.
- Heavily edited AI text with personal details, fragments, and varied punctuation may score as human-like because the signals are based on final surface style, not writing history.
- Very short submissions are not reliable. The implementation forces text under 40 words to `uncertain` because neither signal has enough evidence.

## Spec Reflection

The spec helped most by forcing exact signal outputs, label thresholds, and label text before implementation. Because the spec already said what `phrase_repetition.score`, `rhythm_uniformity.score`, `confidence`, `labelCode`, and `reasons` should look like, the Flask code had a concrete contract to implement instead of a vague "detect AI" goal.

One implementation divergence is that I added `GET /appeals` and `GET /audit/<submissionId>` even though the minimum M5 requirement focused on creating appeals. I added them because they make the reviewer queue and audit trail inspectable during testing and during the portfolio walkthrough. I also added stretch features after updating the spec: a third specificity signal, provenance certificates, analytics, and rate limiting. Another practical divergence is persistence: the design names stores and audit logs, but the MVP uses in-memory data structures so the project stays easy to run locally.

## AI Usage

I used an AI coding assistant for planning, implementation, and documentation, but I kept the system behavior tied to the spec and revised places where the output was too vague or mismatched.

Specific instances:

1. I directed the AI to turn the milestone prompt into an implementation-ready `planning.md`. It produced the two-signal design, scoring thresholds, label variants, appeal workflow, and architecture diagram. I revised the spec to make the score direction explicit (`0.0` human-like, `1.0` AI-like), added a short-text uncertainty override, and corrected a sample reliability value so the spec and implementation would agree.

2. I directed the AI to implement M3, M4, and M5 in separate commits. It produced the Flask app skeleton, signal functions, scoring logic, labels, appeal endpoint, audit helpers, and tests. I checked the scores with concrete inputs, kept the conservative thresholds from the spec, and added tests for all three label variants plus duplicate appeal handling.

3. I directed the AI to expand the README into a submission artifact rather than a feature list. It produced the architecture and design-decision sections. I grounded the examples with actual scores from the running code and revised the rate-limit section after implementing real `429` behavior.

4. I directed the AI to add stretch features only after extending `planning.md`. It produced the first pass of the ensemble signal, certificate endpoint, analytics endpoint, rate limiter, and tests. I revised the scoring weights, made audit entries include `labelCode` and `confidence` at the top level, and kept certificates separate from the standard AI-likelihood label so verification would not erase the attribution result.

## Portfolio Walkthrough Guide

I cannot record audio or a screen from this repo environment, but this is the short walkthrough script I would use for a 2-3 minute portfolio recording.

### Suggested Recording Flow

1. Show `planning.md` briefly and say: "This project started with a spec that defined the signals, confidence thresholds, label text, and appeal flow before implementation."
2. Show `main.py` and point out `score_phrase_repetition`, `score_rhythm_uniformity`, `score_specificity_gap`, `combine_confidence`, `compose_label`, `submit_appeal`, `create_certificate`, and `analytics`.
3. Run the tests:

```bash
python -m unittest -v
```

4. Submit a high-confidence AI-like sample and point out `confidence: 0.94`, `labelCode: likely_ai`, and the three signal scores.
5. Submit a human-like sample and point out `confidence: 0.19`, `labelCode: likely_human`, and the lower signal scores.
6. Submit an appeal for the likely-AI result and show the status changing to `under_review`.
7. Create a provenance certificate and show the separate verified provenance label.
8. Open `/analytics` and point out detection pattern, appeal rate, average confidence, and certificate rate.
9. Open the audit endpoint and point out the `submission_labeled`, `appeal_submitted`, `submission_status_changed`, and `certificate_verified` events.
10. Trigger the submit rate limit and show the `429` response.
11. Close by saying: "The key design decision was not to claim certainty. The project exposes signal evidence, shrinks confidence when evidence is weak, gives users an appeal path, and keeps verification separate from attribution."

### Short Voiceover Draft

```text
This is Provenance Guard, a small Flask service that labels text provenance with transparent uncertainty. I built it from a written spec first, so the implementation had concrete signal outputs, thresholds, label text, and appeal behavior.

The submission endpoint normalizes text, runs three signals, and combines them into an AI-likelihood confidence score. The first signal looks for repeated AI-associated phrasing and repeated structure. The second looks for unusually even rhythm, like low sentence-length variation and limited punctuation variety. The third looks for a specificity gap: generic abstraction without concrete personal detail. I combine them with reliability weights and pull the score toward uncertainty for short text or conflicting signals.

Here is a formulaic repeated sample. It gets a 0.94 confidence and the likely-AI label. Here is a more concrete, uneven personal sample. It gets a 0.19 AI-likelihood score and the likely-human label. A short or mixed sample lands in the uncertain range.

The appeal flow is the accountability layer. When I submit an appeal, the submission moves from labeled to under_review. The system stores the appeal, prevents duplicate open appeals, and writes audit events for the original label and the status change. I also added stretch features: a creator can request a verified provenance certificate, and the analytics endpoint reports detection pattern, appeal rate, average confidence, and certificate rate.

If this were production, I would not ship these heuristics as proof. I would calibrate against real domain data, add authentication, move rate-limit state to a shared store, persist the audit log, and put a human reviewer in front of high-impact decisions.
```
