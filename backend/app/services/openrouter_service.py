import json
import logging
from typing import AsyncGenerator
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

async def stream_openrouter_completion(
    model_string: str,
    system_prompt: str,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """
    Streams tokens from OpenRouter API using an OpenAI-compatible format.
    Accepts system prompt and user messages, and yields text chunks as they arrive.
    """
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not configured.")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.FRONTEND_URL,
        "X-Title": "Enterprise Omni-Modal RAG Vault",
    }

    # Format messages for OpenRouter/OpenAI compatibility
    formatted_messages = []
    if system_prompt:
        formatted_messages.append({"role": "system", "content": system_prompt})
    
    # Add conversation/messages
    formatted_messages.extend(messages)

    payload = {
        "model": model_string,
        "messages": formatted_messages,
        "stream": True,
        "temperature": 0.0,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as response:
            if response.status_code != 200:
                error_body = await response.aread()
                logger.error(
                    "OpenRouter API stream request failed: %s - %s",
                    response.status_code,
                    error_body.decode(errors="ignore"),
                )
                raise Exception(f"OpenRouter API error: {response.status_code}")

            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("data: "):
                    data_str = line[len("data: "):]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        # Sometimes OpenRouter sends metadata comments or empty lines, ignore parse errors
                        logger.debug("Non-JSON line in SSE stream: %s", line)
