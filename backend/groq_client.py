import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY not found. Check the project .env file."
    )

GROQ_MODEL = "qwen/qwen3.8-27b"

_client = Groq(api_key=GROQ_API_KEY)


def generate_ai_response(prompt: str) -> str:
    completion = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0.1,
        max_completion_tokens=2048,
        top_p=0.95,
        stream=False,
    )

    return completion.choices[0].message.content or ""
