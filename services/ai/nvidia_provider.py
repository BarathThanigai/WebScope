import json
import logging
import time

from openai import APIConnectionError, APITimeoutError, BadRequestError, OpenAI, RateLimitError
from pydantic import ValidationError

from models import CrawlReportResponse
from services.ai.prompts import build_audit_summary_messages
from services.ai.provider import (
    AIProvider,
    AIProviderModelError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIMalformedOutputError,
    MissingAIKeyError,
)
from services.ai.schemas import AISummary

logger = logging.getLogger(__name__)


class NvidiaAIProvider(AIProvider):
    def generate_summary(self, report: CrawlReportResponse) -> AISummary:
        if not self.config.api_key:
            raise MissingAIKeyError()

        client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=30.0,
        )

        last_error: Exception | None = None
        for attempt in range(2):
            started_at = time.perf_counter()
            try:
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=build_audit_summary_messages(report),
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or "{}"
                summary = AISummary.model_validate(json.loads(content))
                self._log_result(started_at, True)
                return summary
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                if attempt == 0:
                    continue
                self._log_result(started_at, False)
                raise AIMalformedOutputError() from exc
            except (APITimeoutError, APIConnectionError) as exc:
                self._log_result(started_at, False)
                raise AIProviderTimeoutError() from exc
            except RateLimitError as exc:
                self._log_result(started_at, False)
                raise AIProviderRateLimitError() from exc
            except BadRequestError as exc:
                self._log_result(started_at, False)
                raise AIProviderModelError() from exc

        raise AIMalformedOutputError() from last_error

    def _log_result(self, started_at: float, success: bool) -> None:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "ai_summary provider=%s model=%s latency_ms=%s success=%s",
            self.config.provider,
            self.config.model,
            latency_ms,
            success,
        )
