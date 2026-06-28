# Provenance Guard

Provenance Guard is a lightweight service for tracing text submissions through AI-detection signals, confidence scoring, transparency labels, and an appeal path.

The implementation follows the milestone spec in `planning.md`.

## What is here
- `main.py`: Flask API with submission scoring, transparency labels, appeals, and audit logs
- `planning.md`: detection signal design, uncertainty thresholds, label variants, appeal workflow, API contract, and architecture diagram
- `test_main.py`: unit tests for label reachability and appeal behavior

## Run the service

```bash
pip install -r requirements.txt
python main.py
```

The service starts on Flask's default local development server.

## Run tests

```bash
python -m unittest -v
```

## API endpoints

- `GET /health`: returns service health.
- `POST /submit`: accepts text, runs both detection signals, returns confidence, label text, and reasons.
- `GET /submission/<submissionId>`: returns the stored submission, current status, audit history, and appeal state.
- `POST /appeal`: opens an appeal for an existing submission and marks it `under_review`.
- `GET /appeals?status=open`: returns reviewer queue rows for open appeals.
- `GET /audit/<submissionId>`: returns audit events for a submission.
