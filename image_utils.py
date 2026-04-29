import uuid
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps
from typing import Literal 

ImageType = Literal["fullsize", "preview"]
ImagePhase = Literal["initial", "update"]

IMAGE_DIR = Path("media/images")

def generate_preview(image_name: str) -> str:
    with Image.open(IMAGE_DIR / image_name) as fullsize:
        img_preview = ImageOps.exif_transpose(fullsize)
        img_preview = ImageOps.fit(img_preview, (300, 300), method=Image.Resampling.LANCZOS)
        if img_preview.mode in ("RGBA", "LA", "P"):
            img_preview = img_preview.convert("RGB")
        preview_filename = f"{uuid.uuid4().hex}.jpg"
        preview_filepath = IMAGE_DIR / preview_filename
        img_preview.save(preview_filepath, "JPEG", quality=85, optimize=True)
    return preview_filename

def process_image(image_type: ImageType, content: bytes, *, keep_filename: bool = False, original_filename: str | None = None) -> list[str | None]:

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    with Image.open(BytesIO(content)) as original:

        images: list[str|None]= []

        img_fullsize = ImageOps.exif_transpose(original)

        if img_fullsize.mode in ("RGBA", "LA", "P"):
            img_fullsize = img_fullsize.convert("RGB")

            
        fullsize_filename = f"{uuid.uuid4().hex}.jpg" if not keep_filename else str(original_filename)
        fullsize_filepath = IMAGE_DIR / fullsize_filename
        img_fullsize.save(fullsize_filepath, "JPEG", quality=30, optimize=True)
        images.append(fullsize_filename)

        if image_type == "preview":
            img_preview = ImageOps.exif_transpose(original)

            img_preview = ImageOps.fit(img_preview, (300, 300), method=Image.Resampling.LANCZOS)

            if img_preview.mode in ("RGBA", "LA", "P"):
                img_preview = img_preview.convert("RGB")

            preview_filename = f"{uuid.uuid4().hex}.jpg" if not keep_filename else f"preview_{str(original_filename)}"
            preview_filepath = IMAGE_DIR / preview_filename
            img_preview.save(preview_filepath, "JPEG", quality=85, optimize=True)
            images.append(preview_filename)
        else:
            images.append(None)

    return images


def delete_image(filename: str | None) -> None:
    if filename is None:
        return

    filepath = IMAGE_DIR / filename
    if filepath.exists():
        filepath.unlink()