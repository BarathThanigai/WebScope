import json

from models import CrawlReportResponse


SUMMARY_JSON_SCHEMA = {
    "executive_summary": "1-2 concise sentences",
    "overall_assessment": "1 concise paragraph",
    "key_findings": ["up to 5 short strings"],
    "recommendations": ["up to 5 short strings"],
    "priority_actions": ["up to 5 short strings"],
    "strengths": ["up to 5 short strings"],
    "risk_level": "low|medium|high",
}


def build_audit_summary_messages(report: CrawlReportResponse) -> list[dict[str, str]]:
    payload = {
        "health_score": report.health_score,
        "page_counts": {
            "total_pages": report.total_pages,
            "total_links": report.total_links,
        },
        "seo_issue_counts": {
            "missing_titles": report.missing_titles_count,
            "missing_descriptions": report.missing_descriptions_count,
            "missing_h1": report.missing_h1_count,
            "total_seo_issues": report.seo_issues_count,
        },
        "broken_links": report.broken_links_count,
        "link_issue_summary": {
            "total_link_issues": report.link_issues_count,
            "by_type": report.link_issues_by_type,
        },
        "slow_pages": report.slow_pages_count,
        "average_response_time_ms": round(report.average_response_time_ms, 2),
        "failed_request_reasons": report.failed_by_reason,
        "top_slow_pages": [
            {
                "title": page.title or "Untitled page",
                "response_time_ms": page.response_time_ms,
                "status_code": page.status_code,
            }
            for page in report.top_10_slowest_pages[:5]
        ],
    }

    return [
        {
            "role": "system",
            "content": (
                "You are WebScope's website audit analyst. Return only valid JSON. "
                "Do not include markdown, comments, or extra text. Keep every list to 5 items or fewer."
            ),
        },
        {
            "role": "user",
            "content": (
                "Generate a concise website audit summary from these metrics. "
                "Use practical, prioritized recommendations. Keep the response compact. "
                f"Return JSON matching this schema: {json.dumps(SUMMARY_JSON_SCHEMA)}. "
                f"Audit metrics: {json.dumps(payload, ensure_ascii=False)}"
            ),
        },
    ]
