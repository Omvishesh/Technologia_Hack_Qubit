"""
LLM Client — Shared interface for calling language models with automatic fallback.

Primary: Groq (llama-3.3-70b-versatile) — ultra fast inference (keys #1 -> #2 -> #3)
Fallback: NVIDIA NIM (meta/llama-3.1-70b-instruct) — enterprise cloud inference (keys #1 -> #2 -> #3)
Additional options: Gemini, standard OpenAI
"""

from __future__ import annotations

import json
import logging
from typing import Any
import httpx

from .config import get_settings

logger = logging.getLogger("incident-response.llm")


# ─────────────────────────────────────────────────────────────
# Primary Provider: Groq
# ─────────────────────────────────────────────────────────────

async def _call_groq(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    api_key: str | None = None,
) -> str:
    """Call Groq Cloud API using OpenAI-compatible chat completions endpoint."""
    settings = get_settings()
    api_key = api_key or settings.groq_api_key
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    import asyncio

    async with httpx.AsyncClient(timeout=25.0) as client:
        for attempt in range(3):
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 429:
                # Groq free tier per-minute token burst limit: wait 1.5s and retry
                await asyncio.sleep(1.5)
                continue
            if resp.status_code != 200:
                raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        raise RuntimeError(f"Groq API error 429: Rate limit exceeded after 3 retries")


# ─────────────────────────────────────────────────────────────
# Fallback Provider: NVIDIA NIM
# ─────────────────────────────────────────────────────────────

async def _call_nvidia(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    api_key: str | None = None,
) -> str:
    """Call NVIDIA NIM API using OpenAI-compatible chat completions endpoint."""
    settings = get_settings()
    api_key = api_key or settings.nvidia_api_key
    if not api_key:
        raise ValueError("NVIDIA_API_KEY is not set.")

    url = f"{settings.nvidia_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.nvidia_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"NVIDIA API error {resp.status_code}: {resp.text}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────────────────────
# Optional: Gemini Provider
# ─────────────────────────────────────────────────────────────

async def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> str:
    """Call Google Gemini API."""
    import asyncio
    import google.generativeai as genai

    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.llm_model or "gemini-2.0-flash")
    full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

    def _generate():
        response = model.generate_content(
            full_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        return response.text

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _generate)


# ─────────────────────────────────────────────────────────────
# Public API with Primary -> Secondary Failover
# ─────────────────────────────────────────────────────────────

async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> str:
    """
    Call LLM with key-level failover.

    Default / groq:  Groq #1 -> #2 -> #3 -> NVIDIA #1 -> #2 -> #3
    nvidia:          NVIDIA #1 -> #2 -> #3 -> Groq #1 -> #2 -> #3
    gemini:          Gemini, then the default chain
    Keys that are not set are skipped.
    """
    settings = get_settings()
    provider = settings.llm_provider.lower()

    groq = [(f"Groq #{i}", settings.groq_model, _call_groq, key)
            for i, key in enumerate((settings.groq_api_key, settings.groq_api_key_2, settings.groq_api_key_3), start=1)]
    nvidia = [(f"NVIDIA #{i}", settings.nvidia_model, _call_nvidia, key)
              for i, key in enumerate((settings.nvidia_api_key, settings.nvidia_api_key_2, settings.nvidia_api_key_3), start=1)]
    chain = [c for c in (nvidia + groq if provider == "nvidia" else groq + nvidia) if c[3]]

    if provider == "gemini":
        try:
            return await _call_gemini(system_prompt, user_prompt, temperature, max_tokens)
        except Exception as exc:
            logger.warning("Gemini failed: %s. Falling back to Groq/NVIDIA chain...", exc)

    last_exc: Exception | None = None
    for name, model, call, api_key in chain:
        try:
            logger.info("Calling LLM: %s (%s)", name, model)
            return await call(system_prompt, user_prompt, temperature, max_tokens, api_key=api_key)
        except Exception as exc:
            logger.warning("LLM %s failed: %s. Trying next provider...", name, exc)
            last_exc = exc

    if last_exc is None:
        raise ValueError("No LLM API keys configured (GROQ_API_KEY / NVIDIA_API_KEY).")
    raise RuntimeError(f"All LLM providers failed; last error: {last_exc}") from last_exc


async def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> dict[str, Any] | list[Any]:
    """
    Call LLM and parse output as JSON with robust markdown stripping.
    """
    raw = await call_llm(system_prompt, user_prompt, temperature, max_tokens)

    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM JSON: %s | Raw response: %s", exc, raw[:300])
        raise ValueError(f"LLM did not return valid JSON: {exc}") from exc
