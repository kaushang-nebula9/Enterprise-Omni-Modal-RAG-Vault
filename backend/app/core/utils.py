import json
import logging

logger = logging.getLogger(__name__)


def extract_chart_spec(llm_response: str) -> tuple[str, dict | None]:
    """
    Search the response string for a line starting with CHART_SPEC:
    If found, extract the JSON string after the CHART_SPEC: prefix.
    Parse the JSON. If parsing succeeds, return (cleaned_text, parsed_dict)
    where cleaned_text is the original response with the CHART_SPEC: line stripped out.
    If the line is not found, or JSON parsing fails for any reason,
    return (original_response, None) - never raise, never surface errors to the user.
    """
    if not llm_response:
        return (llm_response, None)

    try:
        # Split the response into lines.
        lines = llm_response.splitlines(keepends=True)
        chart_line_idx = -1
        for idx, line in enumerate(lines):
            if line.strip().startswith("CHART_SPEC:"):
                chart_line_idx = idx
                break

        if chart_line_idx == -1:
            return (llm_response, None)

        target_line = lines[chart_line_idx]
        prefix_idx = target_line.find("CHART_SPEC:")
        json_str = target_line[prefix_idx + len("CHART_SPEC:") :].strip()

        parsed_dict = json.loads(json_str)
        if not isinstance(parsed_dict, dict):
            return (llm_response, None)

        # Build the cleaned response text by removing that exact line.
        cleaned_lines = lines[:chart_line_idx] + lines[chart_line_idx + 1 :]
        cleaned_text = "".join(cleaned_lines).strip()
        return (cleaned_text, parsed_dict)
    except Exception as e:
        logger.error(f"Failed to extract or parse CHART_SPEC: {e}")
        return (llm_response, None)


PROVIDER_REGISTRY = [
    {
        "provider_id": "anthropic",
        "display_name": "Anthropic",
        "sdk_type": "anthropic",
        "requires_base_url": False,
    },
    {
        "provider_id": "openai",
        "display_name": "OpenAI",
        "sdk_type": "openai_compat",
        "requires_base_url": False,
        "default_base_url": "https://api.openai.com/v1",
    },
    {
        "provider_id": "gemini",
        "display_name": "Google Gemini",
        "sdk_type": "google",
        "requires_base_url": False,
    },
    {
        "provider_id": "openrouter",
        "display_name": "OpenRouter",
        "sdk_type": "openai_compat",
        "requires_base_url": False,
        "default_base_url": "https://openrouter.ai/api/v1",
    },
    {
        "provider_id": "mistral",
        "display_name": "Mistral",
        "sdk_type": "openai_compat",
        "requires_base_url": False,
        "default_base_url": "https://api.mistral.ai/v1",
    },
    {
        "provider_id": "custom",
        "display_name": "Custom (OpenAI-compatible)",
        "sdk_type": "openai_compat",
        "requires_base_url": True,
    },
]


def get_provider_by_id(provider_id: str) -> dict:
    for provider in PROVIDER_REGISTRY:
        if provider["provider_id"] == provider_id:
            return provider
    # Fallback to openai_compat (e.g. custom or openai)
    for provider in PROVIDER_REGISTRY:
        if provider["provider_id"] == "custom":
            return provider
    return {
        "provider_id": "custom",
        "display_name": "Custom (OpenAI-compatible)",
        "sdk_type": "openai_compat",
        "requires_base_url": True,
    }


def get_llm_client(model_config):
    provider = get_provider_by_id(model_config.provider_id)
    sdk_type = provider["sdk_type"]

    if sdk_type == "anthropic":
        from anthropic import AsyncAnthropic

        return AsyncAnthropic(api_key=model_config.api_key or "")

    elif sdk_type == "openai_compat":
        from openai import AsyncOpenAI

        base_url = model_config.base_url or provider.get("default_base_url")
        return AsyncOpenAI(api_key=model_config.api_key or "", base_url=base_url)

    elif sdk_type == "google":
        from google import genai

        return genai.Client(api_key=model_config.api_key or "")

    else:
        raise ValueError(f"Unsupported sdk_type: {sdk_type}")
