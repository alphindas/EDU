"""Provider-agnostic LLM wrapper for CHITTI 2.0.

EDUNEST_AI_PROVIDER = stub | openai | gemini
  stub    offline, deterministic (default; no network, no key)
  openai  any OpenAI-compatible Chat Completions API (OpenAI, Azure OpenAI, Groq, OpenRouter, Ollama, vLLM ...)
          EDUNEST_AI_BASE_URL (default https://api.openai.com/v1), EDUNEST_AI_MODEL (default gpt-4o-mini)
  gemini  Google Gemini generateContent API, EDUNEST_AI_MODEL (default gemini-1.5-flash)
EDUNEST_AI_API_KEY holds the key for either.

Privacy: callers only pass academic text, the learner's class band and language. Never names, phones or ids.
If a provider call fails, `ProviderTutor` falls back to the offline stub so a lesson never breaks mid-way."""
import base64
import logging

import httpx

from .config import get_settings

log = logging.getLogger("edunest.ai")

LANG_NAMES = {"en": "English", "te": "Telugu", "hi": "Hindi", "ml": "Malayalam", "ta": "Tamil"}

SAFETY = (
    "You are CHITTI, the friendly robot learning buddy of a school portal called EduNest. "
    "Rules you always follow: keep answers age-appropriate and kind; prefer the school-approved material given to you and "
    "cite it as [source: name]; if you are not sure, say \"I'm not sure\" instead of guessing; never ask for or reveal "
    "personal details; never give medical, legal or clinical diagnoses or label anyone's intelligence or personality; "
    "if a learner seems upset or unsafe, gently suggest talking to a trusted teacher, parent or the school counsellor. "
    "Never do a student's graded work for them without explaining the steps."
)


class LLMError(RuntimeError):
    pass


def configured() -> bool:
    s = get_settings()
    return s.ai_provider in ("openai", "gemini") and bool(s.ai_api_key)


def provider_name() -> str:
    s = get_settings()
    return s.ai_provider if configured() else "stub"


def complete(system: str, messages: list[tuple[str, str]], *, image: tuple[bytes, str] | None = None, max_tokens: int = 900,
             temperature: float = 0.4) -> str:
    """messages = [(role 'user'|'assistant', text)]. image = (bytes, mime) attached to the last user turn."""
    s = get_settings()
    if not configured():
        raise LLMError("no provider configured")
    try:
        if s.ai_provider == "openai":
            return _openai(s, system, messages, image, max_tokens, temperature)
        return _gemini(s, system, messages, image, max_tokens, temperature)
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:  # network, auth, unexpected payload
        log.warning("AI provider call failed: %s", e)
        raise LLMError(str(e)) from e


def _openai(s, system, messages, image, max_tokens, temperature) -> str:
    msgs: list[dict] = [{"role": "system", "content": system}]
    for i, (role, text) in enumerate(messages):
        if image and i == len(messages) - 1 and role == "user":
            url = f"data:{image[1]};base64,{base64.b64encode(image[0]).decode()}"
            msgs.append({"role": "user", "content": [{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": url}}]})
        else:
            msgs.append({"role": role, "content": text})
    r = httpx.post(
        f"{s.ai_base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {s.ai_api_key}"},
        json={"model": s.ai_model or "gpt-4o-mini", "messages": msgs, "max_tokens": max_tokens, "temperature": temperature},
        timeout=s.ai_timeout_seconds,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _gemini(s, system, messages, image, max_tokens, temperature) -> str:
    contents = []
    for i, (role, text) in enumerate(messages):
        parts: list[dict] = [{"text": text}]
        if image and i == len(messages) - 1 and role == "user":
            parts.append({"inline_data": {"mime_type": image[1], "data": base64.b64encode(image[0]).decode()}})
        contents.append({"role": "model" if role == "assistant" else "user", "parts": parts})
    model = s.ai_model or "gemini-1.5-flash"
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": s.ai_api_key},
        json={"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
              "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature}},
        timeout=s.ai_timeout_seconds,
    )  # fmt: skip
    r.raise_for_status()
    cand = r.json()["candidates"][0]
    return "".join(p.get("text", "") for p in cand["content"]["parts"]).strip()


def system_prompt(extra: str = "", lang: str = "en", level: str = "") -> str:
    lname = LANG_NAMES.get(lang, "English")
    lvl = f" The learner is {level}; match vocabulary and depth to that level." if level else ""
    return (f"{SAFETY}{lvl} Reply in {lname} (the user may mix languages; still reply in {lname}). "
            f"Use short paragraphs, simple words and one everyday example. {extra}").strip()


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Real embeddings when the OpenAI-compatible provider is configured with EDUNEST_AI_EMBED_MODEL; else None."""
    s = get_settings()
    if not (configured() and s.ai_provider == "openai" and s.ai_embed_model):
        return None
    try:
        r = httpx.post(f"{s.ai_base_url.rstrip('/')}/embeddings", headers={"Authorization": f"Bearer {s.ai_api_key}"},
                       json={"model": s.ai_embed_model, "input": texts}, timeout=s.ai_timeout_seconds)  # fmt: skip
        r.raise_for_status()
        return [d["embedding"] for d in r.json()["data"]]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        log.warning("embedding call failed: %s", e)
        return None
