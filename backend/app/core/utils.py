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
