import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from main import app
from models import CrawlReportResponse
from services.ai.schemas import AISummary


class FakeDatabase:
    def get_report(self, job_id: str) -> CrawlReportResponse:
        return CrawlReportResponse(
            job_id=job_id,
            total_pages=1,
            total_links=3,
            broken_links_count=0,
            link_issues_count=0,
            link_issues_by_type={},
            slow_pages_count=0,
            skipped_by_robots_count=0,
            timeout_count=0,
            failed_by_reason={},
            missing_titles_count=0,
            missing_descriptions_count=1,
            missing_h1_count=0,
            seo_issues_count=1,
            average_response_time_ms=250.0,
            min_response_time_ms=250.0,
            max_response_time_ms=250.0,
            health_score=96,
            top_10_slowest_pages=[],
        )


class FakeProvider:
    def generate_summary(self, report: CrawlReportResponse) -> AISummary:
        return AISummary(
            executive_summary="The site is healthy with one SEO improvement.",
            overall_assessment="Strong technical baseline.",
            key_findings=["One missing meta description."],
            recommendations=["Add a concise meta description."],
            priority_actions=["Fix missing metadata."],
            strengths=["Fast response time."],
            risk_level="low",
        )


class AISummaryEndpointTests(unittest.TestCase):
    def test_ai_summary_endpoint_returns_validated_json(self) -> None:
        app.dependency_overrides[main.get_database] = lambda: FakeDatabase()
        try:
            with patch("main.get_ai_provider", return_value=FakeProvider()):
                response = TestClient(app).post("/crawl/job-123/ai-summary")
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["risk_level"], "low")
        self.assertEqual(body["priority_actions"], ["Fix missing metadata."])


if __name__ == "__main__":
    unittest.main()
