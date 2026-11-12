"""Upload storage. Files live under <upload_dir>/<school_id>/<category>/<uuid>.<ext>, never under a web root, and are
only served through authenticated routes. Content type is sniffed from the bytes (the client's claim is ignored) and
only an allow-list of non-executable types is accepted (no HTML/SVG/JS)."""
import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from .config import get_settings

IMAGE = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
DOC = {"application/pdf": "pdf"}
AUDIO = {"audio/ogg": "ogg", "audio/webm": "webm", "audio/mpeg": "mp3", "audio/wav": "wav", "audio/mp4": "m4a"}


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"OggS"):
        return "audio/ogg"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data.startswith(b"ID3") or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if data[4:8] == b"ftyp":
        return "audio/mp4"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm"
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
            fmt = (im.format or "").upper()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        return None
    return {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(fmt)


def save_upload(school_id: int, category: str, f: UploadFile, allowed: dict[str, str]) -> tuple[str, str, str]:
    """Validate + store. Returns (relative_path, content_type, original_name). Raises 413/415."""
    s = get_settings()
    limit = s.max_upload_mb * 1024 * 1024
    data = f.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File larger than {s.max_upload_mb} MB")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Empty file")
    ctype = _sniff(data)
    if ctype not in allowed:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported file type")
    rel = f"{school_id}/{category}/{uuid.uuid4().hex}.{allowed[ctype]}"
    path = Path(s.upload_dir) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    name = (f.filename or "file").replace("\\", "/").split("/")[-1][:200]
    return rel, ctype, name


def serve(school_id: int, rel: str, ctype: str, name: str) -> FileResponse:
    """Serve a stored file. Refuses paths outside this school's folder (defence in depth)."""
    base = Path(get_settings().upload_dir).resolve()
    path = (base / rel).resolve()
    if not rel or not str(path).startswith(str(base / str(school_id))) or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return FileResponse(
        path, media_type=ctype, filename=name, content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


def remove(rel: str) -> None:
    if rel:
        try:
            (Path(get_settings().upload_dir) / rel).unlink(missing_ok=True)
        except OSError:
            pass
