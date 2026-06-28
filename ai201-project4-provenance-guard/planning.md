# Provenance Guard Architecture Plan

## Overview
Provenance Guard is designed as a single flow from submission to label, plus a second flow for appeals. The system needs to connect seven features without breaking at the seams:

1. text submission intake
2. preprocessing and normalization
3. detection signal 1
4. detection signal 2
5. confidence scoring
6. transparency labeling
7. audit logging and appeals handling

This plan describes how a single piece of text moves through the service, what each component does, and how we keep the system reliable when the signals disagree.

## Submission Flow Narrative

1. A creator submits text through `POST /submit`.
2. The API receives the raw text and assigns it a submission ID.
3. The text is normalized so the detectors see a clean version of the same content every time.
4. The first detector scores the text for machine-like fluency.
5. The second detector scores the text for stylistic burstiness.
6. The scoring engine combines the two signal scores into one confidence value.
7. The label generator turns that confidence value into a transparency label.
8. The audit logger records the submission, the signal values, the label, and the decision.
9. The API returns the label, confidence, and signal details to the requester.

Every component is part of the same end-to-end path. If any one of them is built in isolation, the system can still fail when theoutputs get merged, so the architecture must make the handoff explicit.

### Components and Roles

- `Submit API` (`POST /submit`): accepts text, returns a submission identifier, and starts the detection path.
- `Normalizer`: cleans whitespace, handles encoding, and prepares the content for scoring.
- `Detector 1`: evaluates fluency / token predictability.
- `Detector 2`: evaluates stylistic burstiness and variation.
- `Scorer`: combines both detector outputs into a confidence score.
- `Label Composer`: converts confidence into a human-friendly transparency label.
- `Audit Logger`: writes every submission and label decision to the audit trail.
- `Response Builder`: packages the label, score, and signals for the client.

## Detection Signals

### Signal 1: Fluency / Token Predictability
- What it measures: how machine-like the text appears in terms of token probability patterns, pacing, and smoothness.
- Why it differs: modern generative models are optimized to produce highly fluent text with fewer unexpected tokens, so AI output often feels even and predictable.
- What it misses: a skilled human writer can also produce polished, even prose; short texts may not contain enough data for a reliable score; heavily edited AI output can hide the signal.

### Signal 2: Burstiness / Stylistic Variation
- What it measures: variability in sentence length, punctuation usage, vocabulary jumps, and structural rhythm.
- Why it differs: human authors usually show more bursts, uneven cadence, and irregular punctuation because real writing comes from thought patterns and edits.
- What it misses: formulaic or highly disciplined human writing can look machine-like; advanced AI can be tuned to add variation; a short submission does not give enough signal.

These two signals are intentionally different. Fluency is about how smooth the text is, while burstiness is about how much it changes over time.

## False Positive Scenario

If a human author is misclassified, the system must still behave responsibly.

1. The author submits a polished paragraph.
2. Signal 1 reports a high machine-like score because the writing is smooth.
3. Signal 2 reports a medium score because the text is balanced but not obviously irregular.
4. The scorer produces a borderline confidence value, for example `0.68`.
5. The label generator should avoid a harsh verdict. The label could read "Potential AI-assisted content" and should include the confidence score.
6. The user can call `POST /appeal` with their submission ID and a short reason.
7. The appeal processor updates the submission status to `under_review`.
8. The audit logger records the appeal event and the status change.
9. The user receives an acknowledgement that the appeal is in review.

This scenario makes it clear that the system should:
- use confidence rather than a hard yes/no edge at first
- pick conservative thresholds for direct AI labels
- keep an appeal path visible and easy to use
- write every decision into the audit log so the review team can see what happened

## API Surface

### POST /submit
- Accepts:
  - `text` (string, required)
  - `authorId` (string, optional)
  - `metadata` (object, optional)
- Returns:
  - `submissionId` (string)
  - `label` (string)
  - `confidence` (number, 0.0 - 1.0)
  - `signals` (object with `fluency` and `burstiness` scores)
  - `status` (string)
  - `message` (string)

### GET /submission/{id}
- Accepts:
  - path parameter `id`
- Returns:
  - `submissionId`
  - `label`
  - `confidence`
  - `status`
  - `signalValues`
  - `auditHistory` (optional list)

### POST /appeal
- Accepts:
  - `submissionId` (string, required)
  - `reason` (string, required)
  - `requester` (string, optional)
- Returns:
  - `appealId` (string)
  - `submissionId` (string)
  - `status` (string)
  - `message` (string)

### GET /audit/{submissionId}
- Accepts:
  - path parameter `submissionId`
- Returns:
  - `submissionId`
  - `auditEntries` (array of timestamped events)

### GET /health
- Returns:
  - `status: "ok"`

## Architecture Diagram

Submission flow:

Client
  ── raw text ──> POST /submit
                 ── raw text ──> Normalizer
                               ── normalized text ──> Detector 1
                                                      ── fluency score ──>
                                                                     Scorer
                                                      ── burstiness score ──>
                                                                     Scorer
                                                                     ── combined confidence ──> Label Composer
                                                                                                 ── label text ──> Audit Logger
                                                                                                 ── label output ──> Response Builder
                                                                                                 ── response ──> Client

Appeal flow:

Client
  ── appeal request ──> POST /appeal
                         ── submissionId + reason ──> Appeal Processor
                                                      ── status update ──> Audit Logger
                                                      ── acknowledgement ──> Response Builder
                                                      ── response ──> Client

## What to Put in `README.md`

The README should summarize this architecture and point readers to `planning.md` for the full design. The main goal for Milestone 1 is not code; it is the path, the signals, the contract, and the diagram that keep the seven features aligned.
