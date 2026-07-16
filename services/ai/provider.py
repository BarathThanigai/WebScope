import os
from abc import ABC, abstractmethod

from models import CrawlReportResponse
from services.ai.schemas import AIProviderConfig, AISummary


class AIProviderError(Exception):
    status_code = 502
    error_type = "provider_unavailable"
    public_message = "AI summary generation failed."


class MissingAIKeyError(AIProviderError):
    status_code = 400
    error_type = "authentication_failed"
    public_message = "AI_API_KEY is required to generate an AI summary."


class AIAuthenticationError(AIProviderError):
    status_code = 401
    error_type = "authentication_failed"
    public_message = "AI provider authentication failed. Check AI_API_KEY."


class AIProviderTimeoutError(AIProviderError):
    status_code = 504
    error_type = "timeout"
    public_message = "AI provider timed out while generating the summary."


class AIProviderRateLimitError(AIProviderError):
    status_code = 429
    error_type = "rate_limited"
    public_message = "AI provider rate limit reached. Please try again later."


class AIProviderModelError(AIProviderError):
    status_code = 400
    error_type = "invalid_model"
    public_message = "The configured AI model is invalid or unavailable."


class AIMalformedOutputError(AIProviderError):
    status_code = 502
    error_type = "malformed_response"
    public_message = "AI provider returned an invalid summary format."


class AIProviderUnavailableError(AIProviderError):
    status_code = 503
    error_type = "provider_unavailable"
    public_message = "AI provider is temporarily unavailable. Please try again later."


class AIProvider(ABC):
    def __init__(self, config: AIProviderConfig) -> None:
        self.config = config

    @abstractmethod
    def generate_summary(self, report: CrawlReportResponse) -> AISummary:
        raise NotImplementedError


def load_ai_config() -> AIProviderConfig:
    try:
        timeout_seconds = float(os.getenv("AI_TIMEOUT_SECONDS", "90"))
    except ValueError:
        timeout_seconds = 90.0

    return AIProviderConfig(
        provider=os.getenv("AI_PROVIDER", "nvidia").lower(),
        api_key=os.getenv("AI_API_KEY"),
        base_url=os.getenv("AI_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        model=os.getenv("AI_MODEL", "z-ai/glm-5.2"),
        timeout_seconds=timeout_seconds,
    )


def get_ai_provider() -> AIProvider:
    config = load_ai_config()
    if config.provider == "nvidia":
        from services.ai.nvidia_provider import NvidiaAIProvider

        return NvidiaAIProvider(config)

    raise AIProviderModelError(f"Unsupported AI provider: {config.provider}")
