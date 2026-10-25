"""이미지를 검사하고 원본을 보존한 회전·자르기·대비 전처리를 제공한다."""
import io
import warnings

import math

from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
SUPPORTED_FORMATS = {"JPEG", "PNG", "MPO", "HEIF"}


def load_image(data: bytes, filename: str) -> Image.Image:
    if not data:
        raise ValueError("빈 파일입니다. 사진을 다시 선택해 주세요.")
    if len(data) > MAX_BYTES:
        raise ValueError("사진은 10MB 이하로 올려 주세요.")
    suffix = filename.rsplit(".", 1)[-1].lower()
    if suffix not in {"jpg", "jpeg", "png", "heic", "heif"}:
        raise ValueError("JPG·PNG·HEIC 사진을 선택해 주세요.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in SUPPORTED_FORMATS:
                    raise ValueError(f"파일 내용은 {image.format or '알 수 없는 형식'}입니다. 확장자만 바꾸지 말고 사진 앱에서 JPG·PNG·HEIC로 내보내 주세요.")
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError("이미지는 2,000만 화소 이하로 줄여 주세요.")
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                # 휴대폰의 HDR/다중 사진 JPEG는 Pillow에서 MPO로 열릴 수 있다.
                # 원본을 바꾸지 않고 첫 번째(대표) 사진만 OCR용으로 읽는다.
                if image.format == "MPO":
                    image.seek(0)
                return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("사진을 열 수 없습니다. 손상되지 않은 JPG·PNG·HEIC 파일로 다시 시도해 주세요.") from exc


def preprocess_image(
    original: Image.Image, rotation: int = 0,
    crop: tuple[float, float, float, float] = (0, 0, 100, 100), contrast: float = 1.0,
) -> Image.Image:
    """원본을 보존한다. 회전 뒤의 사진을 기준으로 백분율 영역을 자른다."""
    if rotation not in {0, 90, 180, 270}:
        raise ValueError("회전은 0·90·180·270도 중 선택해 주세요.")
    if not math.isfinite(contrast) or not 0.5 <= contrast <= 2.0:
        raise ValueError("대비는 0.5~2.0 범위여야 합니다.")
    if len(crop) != 4 or not all(math.isfinite(v) for v in crop):
        raise ValueError("자르기 영역을 확인해 주세요.")
    left, top, right, bottom = crop
    if not (0 <= left < right <= 100 and 0 <= top < bottom <= 100):
        raise ValueError("자르기 시작은 끝보다 작아야 하며 0~100% 범위여야 합니다.")
    image = original.rotate(rotation, expand=True)
    width, height = image.size
    box = (round(left * width / 100), round(top * height / 100), round(right * width / 100), round(bottom * height / 100))
    if box[2] - box[0] < 8 or box[3] - box[1] < 8:
        raise ValueError("성분표 영역을 조금 더 넓게 선택해 주세요.")
    return ImageEnhance.Contrast(image.crop(box)).enhance(contrast)
