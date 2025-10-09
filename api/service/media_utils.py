# service/media_utils.py
import io
import logging
import os
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable, Tuple
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, UnidentifiedImageError, ImageDraw, ImageFont
try:  # optional PDF rendering
    import fitz  # PyMuPDF

    _PDF_ENABLED = True
except Exception:  # pragma: no cover
    _PDF_ENABLED = False

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()  # registers HEIF with Pillow
    _HEIF_ENABLED = True
except Exception:  # pragma: no cover - converter is optional
    _HEIF_ENABLED = False


class MediaValidationError(Exception):
    """Raised when the uploaded file is invalid (type, size, etc)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class MediaProcessingError(Exception):
    """Raised when the image could not be processed."""


@dataclass
class ProcessedImage:
    content: bytes
    mime_type: str
    width: int
    height: int
    extension: str
    display_name: str
    thumbnail: bytes
    thumbnail_mime: str


@dataclass
class ProcessedMedia:
    content: bytes
    mime_type: str
    width: int
    height: int
    extension: str
    display_name: str
    thumbnail: bytes | None
    thumbnail_mime: str | None


_ALLOWED_DEFAULTS = tuple(getattr(settings, "INGRESO_MEDIA_ALLOWED_MIME", ["image/jpeg", "image/png"]))


def _sanitize_display_name(raw_name: str, ext: str) -> str:
    name = os.path.basename(raw_name or "")
    base, _old_ext = os.path.splitext(name)
    base_ascii = base.encode("ascii", errors="ignore").decode("ascii")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", base_ascii).strip("-._")
    if not safe:
        safe = "foto"
    ext = ext.lower().lstrip(".") or "jpg"
    return f"{safe}.{ext}"


def _ensure_allowed(mime: str, allowed: Iterable[str]) -> None:
    allowed_set = {m.lower() for m in (allowed or _ALLOWED_DEFAULTS)}
    if mime.lower() not in allowed_set:
        raise MediaValidationError(f"Formato no permitido: {mime}", status_code=415)


def _image_to_bytes(image: Image.Image, fmt: str, *, jpeg_quality: int = 88) -> Tuple[bytes, str]:
    fmt = fmt.upper()
    buf = io.BytesIO()
    save_kwargs = {"format": fmt}
    if fmt == "JPEG":
        save_kwargs.update({"quality": jpeg_quality, "optimize": True})
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
    elif fmt == "PNG":
        save_kwargs.update({"optimize": True})
        if image.mode not in ("RGB", "RGBA", "L"):
            image = image.convert("RGBA")
    image.save(buf, **save_kwargs)
    return buf.getvalue(), Image.MIME.get(fmt, f"image/{fmt.lower()}")


def process_upload(uploaded_file, *, max_size_bytes: int, thumb_max: int,
                   allowed_mime: Iterable[str] = _ALLOWED_DEFAULTS) -> ProcessedImage:
    size_attr = getattr(uploaded_file, "size", None)
    if size_attr is not None and size_attr > max_size_bytes:
        raise MediaValidationError("Archivo demasiado grande", status_code=413)

    data = uploaded_file.read()
    if not data:
        raise MediaValidationError("Archivo vacio", status_code=400)
    if len(data) > max_size_bytes:
        raise MediaValidationError("Archivo demasiado grande", status_code=413)

    stream = io.BytesIO(data)
    try:
        img = Image.open(stream)
        img.load()
    except UnidentifiedImageError as exc:
        raise MediaValidationError("No se reconoce como imagen", status_code=415) from exc
    except Exception as exc:  # pragma: no cover - unexpected issues
        raise MediaProcessingError("No se pudo procesar la imagen") from exc

    fmt = (img.format or "").upper()
    image = ImageOps.exif_transpose(img)
    try:
        width, height = image.size
    except Exception as exc:
        raise MediaProcessingError("Imagen corrupta") from exc

    if fmt in {"HEIC", "HEIF"}:
        if not _HEIF_ENABLED:
            raise MediaValidationError("Formato HEIC no soportado en este entorno", status_code=415)
        fmt = "JPEG"

    mime = Image.MIME.get(fmt.upper(), f"image/{fmt.lower()}")
    _ensure_allowed(mime, allowed_mime)

    original_bytes, mime = _image_to_bytes(image, fmt)

    if len(original_bytes) > max_size_bytes:
        raise MediaValidationError("Archivo excede el limite luego de normalizar", status_code=413)

    thumb = image.copy()
    try:
        thumb.thumbnail((thumb_max, thumb_max), Image.Resampling.LANCZOS)
    except Exception:
        thumb = image.copy()
        thumb.thumbnail((thumb_max, thumb_max))
    thumb_bytes, thumb_mime = _image_to_bytes(thumb, "JPEG", jpeg_quality=82)

    display_name = _sanitize_display_name(getattr(uploaded_file, "name", ""), fmt.lower())

    return ProcessedImage(
        content=original_bytes,
        mime_type=mime,
        width=width,
        height=height,
        extension=fmt.lower(),
        display_name=display_name,
        thumbnail=thumb_bytes,
        thumbnail_mime=thumb_mime,
    )


def _guess_mime_from_name(name: str) -> tuple[str, str]:
    base = os.path.basename(name or "").lower()
    _, ext = os.path.splitext(base)
    e = ext.lstrip(".")
    if e == "pdf":
        return "application/pdf", "pdf"
    if e in ("mp4",):
        return "video/mp4", e
    if e in ("jpg", "jpeg"):
        return "image/jpeg", e
    if e == "png":
        return "image/png", e
    return "application/octet-stream", e or "bin"


def _make_placeholder_thumb(label: str, size: int = 256) -> tuple[bytes, str]:
    img = Image.new("RGB", (size, size), color=(230, 235, 240))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    text = label.upper()[:8]
    tw, th = d.textsize(text, font=font)
    d.rectangle([(0, size - 28), (size, size)], fill=(210, 215, 220))
    d.text(((size - tw) // 2, (size - th) // 2), text, fill=(30, 30, 30), font=font)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82, optimize=True)
    return buf.getvalue(), "image/jpeg"


def _make_pdf_thumb(pdf_bytes: bytes, thumb_max: int) -> tuple[bytes, str] | tuple[None, None]:
    if not _PDF_ENABLED:
        return None, None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count < 1:
            return None, None
        page = doc.load_page(0)
        # Render base pixmap; scale up a bit for quality, Pillow will downscale
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        # Create square-ish thumbnail preserving aspect
        img.thumbnail((thumb_max, thumb_max), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return None, None


def process_upload_any(uploaded_file, *, max_size_bytes: int, thumb_max: int,
                       allowed_mime: Iterable[str] = _ALLOWED_DEFAULTS) -> ProcessedMedia:
    size_attr = getattr(uploaded_file, "size", None)
    if size_attr is not None and size_attr > max_size_bytes:
        raise MediaValidationError("Archivo demasiado grande", status_code=413)

    data = uploaded_file.read()
    if not data:
        raise MediaValidationError("Archivo vacio", status_code=400)
    if len(data) > max_size_bytes:
        raise MediaValidationError("Archivo demasiado grande", status_code=413)

    # Intentar como imagen primero
    try:
        stream = io.BytesIO(data)
        img = Image.open(stream)
        img.load()
        fmt = (img.format or "").upper()
        image = ImageOps.exif_transpose(img)
        width, height = image.size
        if fmt in {"HEIC", "HEIF"}:
            if not _HEIF_ENABLED:
                raise MediaValidationError("Formato HEIC no soportado en este entorno", status_code=415)
            fmt = "JPEG"
        mime = Image.MIME.get(fmt.upper(), f"image/{fmt.lower()}")
        _ensure_allowed(mime, allowed_mime)
        original_bytes, mime = _image_to_bytes(image, fmt)
        if len(original_bytes) > max_size_bytes:
            raise MediaValidationError("Archivo excede el limite luego de normalizar", status_code=413)
        thumb = image.copy()
        try:
            thumb.thumbnail((thumb_max, thumb_max), Image.Resampling.LANCZOS)
        except Exception:
            thumb = image.copy()
            thumb.thumbnail((thumb_max, thumb_max))
        thumb_bytes, thumb_mime = _image_to_bytes(thumb, "JPEG", jpeg_quality=82)
        display_name = _sanitize_display_name(getattr(uploaded_file, "name", ""), fmt.lower())
        return ProcessedMedia(
            content=original_bytes,
            mime_type=mime,
            width=width,
            height=height,
            extension=fmt.lower(),
            display_name=display_name,
            thumbnail=thumb_bytes,
            thumbnail_mime=thumb_mime,
        )
    except UnidentifiedImageError:
        pass
    except MediaValidationError:
        raise
    except Exception:
        pass

    # Si no es imagen: PDF / video / otros permitidos
    content_type = getattr(uploaded_file, "content_type", "") or ""
    if not content_type or content_type == "application/octet-stream":
        guessed_mime, guessed_ext = _guess_mime_from_name(getattr(uploaded_file, "name", ""))
    else:
        guessed_mime, guessed_ext = content_type, _guess_mime_from_name(getattr(uploaded_file, "name", ""))[1]
    _ensure_allowed(guessed_mime, allowed_mime)

    ext = guessed_ext or {
        "application/pdf": "pdf",
        "video/mp4": "mp4",
    }.get(guessed_mime, "bin")
    display_name = _sanitize_display_name(getattr(uploaded_file, "name", ""), ext)

    thumb_bytes = None
    thumb_mime = None
    if guessed_mime == "application/pdf":
        tb, tm = _make_pdf_thumb(data, thumb_max)
        if tb and tm:
            thumb_bytes, thumb_mime = tb, tm
    if thumb_bytes is None:
        try:
            label = "PDF" if guessed_mime == "application/pdf" else ("VIDEO" if guessed_mime.startswith("video/") else "FILE")
            thumb_bytes, thumb_mime = _make_placeholder_thumb(label, size=min(thumb_max, 512))
        except Exception:
            thumb_bytes, thumb_mime = None, None

    return ProcessedMedia(
        content=data,
        mime_type=guessed_mime,
        width=0,
        height=0,
        extension=ext,
        display_name=display_name,
        thumbnail=thumb_bytes,
        thumbnail_mime=thumb_mime,
    )


def save_processed_image(ingreso_id: int, processed: ProcessedImage) -> Tuple[str, str]:
    prefix = getattr(settings, "INGRESO_MEDIA_STORAGE_PREFIX", "ingresos").strip().strip("/") or "ingresos"
    folder = PurePosixPath(prefix) / str(ingreso_id) / "fotos"
    token = uuid4().hex
    original_name = f"{token}.{processed.extension}"
    thumb_name = f"{token}_thumb.jpg"

    orig_path = str(folder / original_name)
    thumb_path = str(folder / thumb_name)

    try:
        stored_path = default_storage.save(orig_path, ContentFile(processed.content))
        stored_thumb = default_storage.save(thumb_path, ContentFile(processed.thumbnail))
    except Exception as exc:
        logger.exception("Fallo al guardar imagen de ingreso", exc_info=exc)
        raise MediaProcessingError("No se pudo guardar la imagen") from exc

    return stored_path, stored_thumb


def delete_media_paths(paths: Iterable[str]) -> None:
    for path in filter(None, paths):
        try:
            if default_storage.exists(path):
                default_storage.delete(path)
        except Exception:
            logger.warning("No se pudo eliminar el archivo de media: %s", path, exc_info=True)


def save_processed_media(ingreso_id: int, processed: ProcessedMedia) -> Tuple[str, str]:
    prefix = getattr(settings, "INGRESO_MEDIA_STORAGE_PREFIX", "ingresos").strip().strip("/") or "ingresos"
    folder = PurePosixPath(prefix) / str(ingreso_id) / "fotos"
    token = uuid4().hex
    original_name = f"{token}.{processed.extension or 'bin'}"
    orig_path = str(folder / original_name)

    try:
        stored_path = default_storage.save(orig_path, ContentFile(processed.content))
    except Exception as exc:
        logger.exception("Fallo al guardar archivo de ingreso", exc_info=exc)
        raise MediaProcessingError("No se pudo guardar el archivo") from exc

    thumb_path = ""
    if processed.thumbnail:
        try:
            thumb_name = f"{token}_thumb.jpg"
            thumb_path = str(folder / thumb_name)
            default_storage.save(thumb_path, ContentFile(processed.thumbnail))
        except Exception:
            thumb_path = ""

    return stored_path, thumb_path
