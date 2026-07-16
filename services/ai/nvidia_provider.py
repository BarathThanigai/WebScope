import json
import logging
import time

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    RateLimitError,
)
from pydantic import ValidationError

from models import CrawlReportResponse
from services.ai.prompts import build_audit_summary_messages
from services.ai.provider import (
    AIProvider,
    AIAuthenticationError,
    AIProviderModelError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
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
            timeout=self.config.timeout_seconds,
        )

        last_error: Exception | None = None
        for attempt in range(2):
            started_at = time.perf_counter()
            try:
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=build_audit_summary_messages(report),
                    temperature=0.1,
                    max_tokens=700,
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
                last_error = exc
                if attempt == 0:
                    self._backoff(attempt)
                    continue
                self._log_result(started_at, False)
                raise AIProviderTimeoutError() from exc
            except RateLimitError as exc:
                self._log_result(started_at, False)
                raise AIProviderRateLimitError() from exc
            except AuthenticationError as exc:
                self._log_result(started_at, False)
                raise AIAuthenticationError() from exc
            except (BadRequestError, NotFoundError) as exc:
                self._log_result(started_at, False)
                raise AIProviderModelError() from exc
            except APIStatusError as exc:
                last_error = exc
                if exc.status_code >= 500 and attempt == 0:
                    self._backoff(attempt)
                    continue
                self._log_result(started_at, False)
                if exc.status_code >= 500:
                    raise AIProviderUnavailableError() from exc
                raise AIProviderModelError() from exc

        self._log_result(time.perf_counter(), False)
        if isinstance(last_error, (APITimeoutError, APIConnectionError)):
            raise AIProviderTimeoutError() from last_error
        raise AIProviderUnavailableError() from last_error

    def _backoff(self, attempt: int) -> None:
        time.sleep(1.5 * (2**attempt))

    def _log_result(self, started_at: float, success: bool) -> None:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "ai_summary provider=%s model=%s latency_ms=%s success=%s",
            self.config.provider,
            self.config.model,
            latency_ms,
            success,
        )
