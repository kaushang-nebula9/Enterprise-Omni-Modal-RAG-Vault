"""
Embedding service using Google Gemini for text embeddings, audio transcription,
and slide image description.
"""
import time
import logging
from google import genai
from google.genai import types as genai_types
from app.core.config import settings

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Lazily initialise and return the Gemini client."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def embed_text(text: str) -> list[float]:
    """
    Generate a text embedding using the gemini-embedding-2-preview model.

    Adds a 0.5-second delay after the API call to avoid rate limiting.
    Raises an exception with a clear message if the call fails.
    """
    client = _get_client()
    try:
        result = client.models.embed_content(
            model="gemini-embedding-2-preview",
            contents=text,
        )
        time.sleep(0.5)
        return result.embeddings[0].values
    except Exception as exc:
        raise RuntimeError(f"Failed to generate embedding: {exc}") from exc


def transcribe_audio(file_path: str) -> str:
    """
    Transcribe an audio file using Gemini 2.5 Flash multimodal.

    Loads the audio from the given absolute path, sends it to the model with a
    transcription prompt, and returns the transcription text.
    Raises an exception with a clear message if transcription fails.
    """
    client = _get_client()
    try:
        with open(file_path, "rb") as f:
            audio_bytes = f.read()

        # Determine MIME type from extension
        ext = file_path.rsplit(".", 1)[-1].lower()
        mime_map = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4"}
        mime_type = mime_map.get(ext, "audio/mpeg")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                genai_types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                "Transcribe this audio file accurately. Return only the transcription text, nothing else.",
            ],
        )
        return response.text or ""
    except Exception as exc:
        raise RuntimeError(f"Failed to transcribe audio '{file_path}': {exc}") from exc


def describe_pptx_slides(file_path: str) -> dict[int, str]:
    """
    Upload an entire PPTX file to Gemini 2.5 and get visual content descriptions
    for every slide in a single API call.

    Returns a dict mapping slide_number (int) to visual_description (str).
    Returns an empty dict on failure to avoid crashing the pipeline.
    """
    import json
    import google.generativeai as genai_legacy

    client = _get_client()
    try:
        # Upload the PPTX via the Gemini file API
        genai_legacy.configure(api_key=settings.GEMINI_API_KEY)
        uploaded_file = genai_legacy.upload_file(
            file_path,
            mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

        prompt = (
            "This is a PowerPoint presentation. For each slide, describe all visual content "
            "in detail - including charts, graphs, diagrams, tables, images, icons, and any "
            "other visual elements. Be specific about data values, labels, trends, colors "
            "used to encode meaning, and key takeaways from each visual.\n\n"
            "Respond in the following JSON format only, with no additional text:\n"
            "{\n"
            '  "slides": [\n'
            "    {\n"
            '      "slide_number": 1,\n'
            '      "visual_description": "Description of all visual content on this slide. '
            'If the slide has no visual content beyond text, return an empty string."\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[uploaded_file, prompt],
        )

        raw_text = (response.text or "").strip()

        # Strip markdown code fences if the model wraps the JSON
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1]  # remove first ```json line
            if raw_text.endswith("```"):
                raw_text = raw_text[: -len("```")].strip()

        data = json.loads(raw_text)
        result: dict[int, str] = {}
        for slide in data.get("slides", []):
            slide_num = int(slide.get("slide_number", 0))
            desc = slide.get("visual_description", "")
            if slide_num > 0:
                result[slide_num] = desc
        return result

    except Exception as exc:
        logger.warning("Failed to describe PPTX slides '%s': %s", file_path, exc)
        return {}
