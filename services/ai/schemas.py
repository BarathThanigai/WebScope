from pydantic import BaseModel, Field


class AISummary(BaseModel):
    executive_summary: str
    overall_assessment: str
    key_findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    priority_actions: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risk_level: str = Field(pattern="^(low|medium|high)$")


class AIProviderConfig(BaseModel):
    provider: str
    api_key: str | None = None
    base_url: str
    model: str
    timeout_seconds: float = 90.0
