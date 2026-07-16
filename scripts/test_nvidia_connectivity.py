import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI


def main() -> None:
    load_dotenv()

    provider = os.getenv("AI_PROVIDER", "nvidia")
    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL", "https://integrate.api.nvidia.com/v1")
    model = os.getenv("AI_MODEL", "z-ai/glm-5.2")
    timeout = float(os.getenv("AI_TIMEOUT_SECONDS", "90"))

    if not api_key:
        print(f"provider={provider} model={model} success=False error=missing_api_key")
        raise SystemExit(1)

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    started_at = time.perf_counter()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Return only valid JSON.",
                },
                {
                    "role": "user",
                    "content": 'Reply with {"ok": true}.',
                },
            ],
            temperature=0.0,
            max_tokens=30,
            response_format={"type": "json_object"},
        )
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        success = parsed.get("ok") is True
        print(
            f"provider={provider} model={model} "
            f"latency_ms={latency_ms} success={success}"
        )
        raise SystemExit(0 if success else 1)
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        print(
            f"provider={provider} model={model} "
            f"latency_ms={latency_ms} success=False error={type(exc).__name__}"
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
