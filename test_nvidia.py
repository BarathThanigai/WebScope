import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("AI_API_KEY")
base_url = os.getenv("AI_BASE_URL", "https://integrate.api.nvidia.com/v1")
model = os.getenv("AI_MODEL", "z-ai/glm-5.2")

print("Starting NVIDIA API test...", flush=True)
print("Base URL:", base_url, flush=True)
print("Model:", model, flush=True)
print("API key loaded:", bool(api_key), flush=True)

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    timeout=30.0,
    max_retries=0,
)

print("Sending request...", flush=True)
started = time.perf_counter()

try:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: API working",
            }
        ],
        max_tokens=20,
        temperature=0,
    )

    elapsed = time.perf_counter() - started
    print("Success", flush=True)
    print("Latency:", round(elapsed, 2), "seconds", flush=True)
    print("Response:", response.choices[0].message.content, flush=True)

except Exception as exc:
    elapsed = time.perf_counter() - started
    print("Failed after:", round(elapsed, 2), "seconds", flush=True)
    print("Error type:", type(exc).__name__, flush=True)
    print("Error:", str(exc), flush=True)