"""Image checks and resizing (ADR-0014). Pillow decides what a file is, never its name."""

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
PHOTO_WIDTHS = {"sm": 400, "md": 800, "lg": 1600}
LOGO_WIDTHS = {"sm": 160, "md": 480}

# Refuse decompression bombs: Pillow raises DecompressionBombError above twice this.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class ImageRejected(ValueError):
    """The upload is not an acceptable image; the message is shown to staff."""


@dataclass(frozen=True)
class Variant:
    name: str
    data: bytes
    width: int
    height: int


def process(data: bytes, *, logo: bool = False) -> list[Variant]:
    """Validate, re-encode (dropping all metadata) and resize to WebP variants."""
    if len(data) > MAX_BYTES:
        raise ImageRejected("Images can be up to 8 MB.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            probe.verify()  # structure check without decoding pixels
        if fmt not in ALLOWED_FORMATS:
            raise ImageRejected("Upload a JPEG, PNG or WebP image.")
        with Image.open(io.BytesIO(data)) as opened:
            if opened.width * opened.height > MAX_PIXELS:
                raise ImageRejected(
                    "That image is too large in pixels. Use one under 40 megapixels."
                )
            opened.load()
            rotated: Image.Image = ImageOps.exif_transpose(opened)  # phone rotation first
            keep_alpha = logo and rotated.mode in ("RGBA", "LA", "P")
            img = rotated.convert("RGBA" if keep_alpha else "RGB")
    except ImageRejected:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        raise ImageRejected(
            "That file is not an image we can use. Upload a JPEG, PNG or WebP."
        ) from None
    if not logo and (img.width < 400 or img.height < 250):
        raise ImageRejected("Photos need to be at least 400 by 250 pixels.")

    out = []
    for name, width in (LOGO_WIDTHS if logo else PHOTO_WIDTHS).items():
        w = min(width, img.width)  # never enlarge
        h = max(1, round(img.height * w / img.width))
        resized = img if w == img.width else img.resize((w, h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        # A fresh save writes no EXIF, XMP or ICC text chunks from the original.
        resized.save(buf, "WEBP", quality=80, method=4)
        out.append(Variant(name, buf.getvalue(), w, h))
    return out
