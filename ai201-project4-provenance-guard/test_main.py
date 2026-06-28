import unittest

from main import APPEALS, AUDIT_LOG, SUBMISSIONS, create_app


AI_LIKE_TEXT = (
    "Overall this process is important to note because clear planning plays a crucial role "
    "in student success. Overall this process is important to note because clear planning "
    "plays a crucial role in team success. Overall this process is important to note because "
    "consistent practice creates meaningful progress every week. Overall this process is "
    "important to note because consistent practice creates meaningful growth every week. "
    "Overall this process is important to note because structured reflection supports better "
    "outcomes over time. Overall this process is important to note because structured "
    "reflection supports stronger outcomes over time. Overall this process is important to "
    "note because learners benefit from clear goals and clear progress. Overall this process "
    "is important to note because teams benefit from clear goals and clear progress. Overall "
    "this process is important to note because in conclusion effective habits improve results. "
    "Overall this process is important to note because as a result effective habits improve "
    "outcomes."
)

HUMAN_LIKE_TEXT = (
    "I wrote the first draft at my kitchen table after the power flickered twice. The dog "
    "kept pushing his nose under my elbow, so one sentence ended up half-finished. Later, I "
    "crossed out the tidy paragraph about discipline and added the bus ride instead: rain on "
    "the windows, my shoes soaked, and my brother laughing because I forgot my lunch again. "
    "Some of it still feels uneven. That is probably the point!"
)


class ProvenanceGuardTestCase(unittest.TestCase):
    def setUp(self) -> None:
        SUBMISSIONS.clear()
        APPEALS.clear()
        AUDIT_LOG.clear()
        self.client = create_app().test_client()

    def test_submit_reaches_all_label_variants(self) -> None:
        ai_response = self.client.post("/submit", json={"text": AI_LIKE_TEXT}).get_json()
        human_response = self.client.post("/submit", json={"text": HUMAN_LIKE_TEXT}).get_json()
        short_response = self.client.post("/submit", json={"text": "Short polished answer with overall clarity."}).get_json()

        self.assertEqual(ai_response["labelCode"], "likely_ai")
        self.assertIn("Likely AI-generated or AI-assisted", ai_response["labelText"])
        self.assertEqual(human_response["labelCode"], "likely_human")
        self.assertIn("Likely human-written", human_response["labelText"])
        self.assertEqual(short_response["labelCode"], "uncertain")
        self.assertIn("Uncertain provenance", short_response["labelText"])

    def test_appeal_updates_status_and_logs_audit(self) -> None:
        submission = self.client.post("/submit", json={"text": AI_LIKE_TEXT}).get_json()
        appeal = self.client.post(
            "/appeal",
            json={
                "submissionId": submission["submissionId"],
                "requester": "student@example.com",
                "reason": "I wrote this myself and can provide draft history.",
                "requestedLabel": "likely_human",
                "evidenceSummary": "I have revision history and outline notes.",
            },
        )

        self.assertEqual(appeal.status_code, 201)
        appeal_data = appeal.get_json()
        self.assertEqual(appeal_data["appealStatus"], "open")
        self.assertEqual(appeal_data["submissionStatus"], "under_review")

        lookup = self.client.get(f"/submission/{submission['submissionId']}").get_json()
        self.assertEqual(lookup["status"], "under_review")
        self.assertEqual(lookup["appealStatus"], "open")

        audit = self.client.get(f"/audit/{submission['submissionId']}").get_json()
        event_types = [event["eventType"] for event in audit["auditEntries"]]
        self.assertIn("appeal_submitted", event_types)
        self.assertIn("submission_status_changed", event_types)

    def test_duplicate_appeal_returns_existing_open_appeal(self) -> None:
        submission = self.client.post("/submit", json={"text": AI_LIKE_TEXT}).get_json()
        payload = {
            "submissionId": submission["submissionId"],
            "requester": "student@example.com",
            "reason": "I wrote this myself and can provide draft history.",
        }

        first_appeal = self.client.post("/appeal", json=payload).get_json()
        second_appeal = self.client.post("/appeal", json=payload)

        self.assertEqual(second_appeal.status_code, 200)
        self.assertEqual(second_appeal.get_json()["appealId"], first_appeal["appealId"])
        self.assertEqual(len(APPEALS), 1)


if __name__ == "__main__":
    unittest.main()
