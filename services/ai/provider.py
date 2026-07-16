import os
from abc import ABC, abstractmethod

from models import CrawlReportResponse
from services.ai.schemas import AIProviderConfig, AISummary


class AIProviderError(Exception):
    status_code = 502
    public_message = "AI summary generation failed."


class MissingAIKeyError(AIProviderError):
    status_code = 400
    public_message = "AI_API_KEY is required to generate an AI summary."


class AIProviderTimeoutError(AIProviderError):
    status_code = 504
    public_message = "AI provider timed out while generating the summary."


class AIProviderRateLimitError(AIProviderError):
    status_code = 429
    public_message = "AI provider rate limit reached. Please try again later."


class AIProviderModelError(AIProviderError):
    status_code = 400
    public_message = "The configured AI model is invalid or unavailable."


class AIMalformedOutputError(AIProviderError):
    status_code = 502
    public_message = "AI provider returned an invalid summary format."


class AIProvider(ABC):
    def __init__(self, config: AIProviderConfig) -> None:
        self.config = config

    @abstractmethod
    def generate_summary(self, report: CrawlReportResponse) -> AISummary:
        raise NotImplementedError


def load_ai_config() -> AIProviderConfig:
    return AIProviderConfig(
        provider=os.getenv("AI_PROVIDER", "nvidia").lower(),
        api_key=os.getenv("AI_API_KEY"),
        base_url=os.getenv("AI_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        model=os.getenv("AI_MODEL", "z-ai/glm-5.2"),
    )


def get_ai_provider() -> AIProvider:
    config = load_ai_config()
    if config.provider == "nvidia":
        from services.ai.nvidia_provider import NvidiaAIProvider

        return NvidiaAIProvider(config)

    raise AIProviderModelError(f"Unsupported AI provider: {config.provider}")
