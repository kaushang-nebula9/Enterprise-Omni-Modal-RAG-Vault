"""
Filesystem storage service for saving and managing uploaded document files.
"""
import os
import logging
from fastapi import UploadFile

logger = logging.getLogger(__name__)

# The backend root directory (one level above this file's package)
_BACKEND_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def save_file(file: UploadFile, tenant_id: str, document_id: str) -> str:
    """
    Save an uploaded file to the filesystem.

    Path: backend/uploads/{tenant_id}/{document_id}/{filename}
    Creates parent directories if they do not exist.

    Returns the relative file path (relative to the backend root directory).
    """
    relative_dir = os.path.join("uploads", str(tenant_id), str(document_id))
    absolute_dir = os.path.join(_BACKEND_ROOT, relative_dir)
    os.makedirs(absolute_dir, exist_ok=True)

    safe_filename = os.path.basename(file.filename or "upload")
    absolute_path = os.path.join(absolute_dir, safe_filename)
    relative_path = os.path.join(relative_dir, safe_filename)

    with open(absolute_path, "wb") as f:
        content = file.file.read()
        f.write(content)

    logger.info("Saved file to %s", absolute_path)
    return relative_path


def delete_file(file_path: str) -> None:
    """
    Delete the file at the given relative path.
    Silently ignores the error if the file does not exist.
    """
    absolute_path = get_absolute_path(file_path)
    try:
        os.remove(absolute_path)
        logger.info("Deleted file: %s", absolute_path)
    except FileNotFoundError:
        logger.debug("File not found (skipping delete): %s", absolute_path)
    except OSError as exc:
        logger.error("Error deleting file %s: %s", absolute_path, exc)


def get_absolute_path(file_path: str) -> str:
    """
    Convert a relative file path (relative to the backend root) to an absolute path.
    """
    return os.path.join(_BACKEND_ROOT, file_path)
