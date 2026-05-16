import google.generativeai as genai
from functools import lru_cache
from backend.config import get_settings

GEMINI_MODEL = "gemini-2.0-flash"


@lru_cache
def get_model() -> genai.GenerativeModel:
    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(GEMINI_MODEL)


def generate(prompt: str, max_tokens: int = 400) -> str | None:
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    try:
        model = get_model()
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.3,
            ),
        )
        return response.text
    except Exception as e:
        print(f"[Gemini] error: {e}")
        return None
