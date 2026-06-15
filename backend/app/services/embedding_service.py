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


def describe_slide_image(image_path: str) -> str:
    """
    Generate a detailed description of a slide image using Gemini Vision.

    Loads the image from the given path, sends it to Gemini with a description
    prompt, and returns the description.
    Returns an empty string on failure to avoid crashing the pipeline.
    """
    client = _get_client()
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[
                genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                (
                    "Describe all visual content in this slide in detail. "
                    "Include descriptions of any charts, graphs, diagrams, tables, images, "
                    "or any other visual elements. Be specific about data, labels, trends, "
                    "and key takeaways visible in the visuals. "
                    "Return only the description, nothing else."
                ),
            ],
        )
        return response.text or ""
    except Exception as exc:
        logger.warning("Failed to describe slide image '%s': %s", image_path, exc)
        return ""
