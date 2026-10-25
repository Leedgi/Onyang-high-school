"""AI가 검출한 글자 위치·내용으로 전성분 영역을 고르고 영상 보정을 적용한다."""
from dataclasses import dataclass
import math
from statistics import median

import cv2
import numpy as np
from PIL import Image

from core.database import IngredientDatabase
from core.ingredient_text import heading_span, ingredient_drafts, section_end_span
from core.models import OCRResult


@dataclass(frozen=True)
class Region:
    box: tuple[int, int, int, int]
    method: str
    text_height: float
    score: float


def _line_regions(ocr: OCRResult):
    blocks = {block.source_index: block for block in ocr.blocks}
    output = []
    for line in ocr.lines:
        points = [point for index in line.source_indices if index in blocks for point in blocks[index].bbox]
        if points:
            xs, ys = zip(*points)
            output.append((line, (min(xs), min(ys), max(xs), max(ys))))
    return sorted(output, key=lambda item: item[1][1])


def locate_region(ocr: OCRResult, size: tuple[int, int], database: IngredientDatabase) -> Region:
    width, height = size
    rows = _line_regions(ocr)
    if not rows:
        return Region((0, 0, width, height), "not_found", 16, 0)
    seeds = []
    for index, (line, bounds) in enumerate(rows):
        if heading_span(line.raw_text):
            seeds.append((100.0, index, "heading"))
        elif not section_end_span(line.raw_text):
            subset = OCRResult("ok", line.raw_text, ocr.blocks, (line,))
            drafts = ingredient_drafts(subset, database)
            exact = sum(draft.status in {"exact", "alias"} for draft in drafts)
            if exact and (len(drafts) == 1 or exact / len(drafts) >= 0.35):
                seeds.append((10 + exact / max(1, len(drafts)), index, "dictionary"))
    if not seeds:
        return Region((0, 0, width, height), "not_found", 16, 0)
    score, start, method = max(seeds, key=lambda seed: (seed[0], -seed[1]))
    if method == "dictionary":
        # 표지를 놓쳤어도 중간의 잘 읽힌 줄만 자르지 않고 위의 인접한 성분 줄을 포함한다.
        while start > 0:
            previous, bounds = rows[start - 1]
            current = rows[start][1]
            previous_height, current_height = bounds[3] - bounds[1], current[3] - current[1]
            overlap = max(0, min(bounds[2], current[2]) - max(bounds[0], current[0]))
            if (section_end_span(previous.raw_text) or current[1] - bounds[3] > max(previous_height, current_height) * 2.2
                    or not 0.5 <= previous_height / max(1, current_height) <= 1.8
                    or overlap < min(bounds[2] - bounds[0], current[2] - current[0]) * 0.3):
                break
            start -= 1
    anchor = rows[start][1]
    typical = max(4.0, median(bounds[3] - bounds[1] for _, bounds in rows[start:]))
    selected = []
    stop_top = None
    previous_bottom = anchor[3]
    for line, bounds in rows[start:]:
        left, top, right, bottom = bounds
        if selected and section_end_span(line.raw_text):
            stop_top = top
            break
        if top - previous_bottom > typical * 2.2:
            break
        if selected and bottom - top > typical * 2.5:
            break
        # 다른 열·배경의 글자를 성분표와 합치지 않는다.
        overlap = max(0, min(right, anchor[2]) - max(left, anchor[0]))
        if overlap < min(right - left, anchor[2] - anchor[0]) * 0.15:
            continue
        selected.append(bounds)
        previous_bottom = max(previous_bottom, bottom)
    if not selected:
        return Region((0, 0, width, height), "not_found", typical, 0)
    pad = max(8, typical * 0.6)
    lower_edge = max(b[3] for b in selected) + pad
    if stop_top is not None:
        lower_edge = max(lower_edge, stop_top - max(2, typical * 0.15))
        lower_edge = min(lower_edge, stop_top)
    box = (
        max(0, math.floor(min(b[0] for b in selected) - pad)),
        max(0, math.floor(min(b[1] for b in selected) - pad)),
        min(width, math.ceil(max(b[2] for b in selected) + pad)),
        min(height, math.ceil(lower_edge)),
    )
    return Region(box, method, typical, score)


def estimate_skew(image: Image.Image) -> float:
    probe = image.copy()
    probe.thumbnail((1200, 800))
    gray = cv2.cvtColor(np.asarray(probe.convert("RGB")), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 360, threshold=35,
                            minLineLength=max(30, probe.width // 8), maxLineGap=12)
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if -10 <= angle <= 10:
            angles.append(angle)
    return float(median(angles)) if len(angles) >= 3 else 0.0


def prepare_region(original: Image.Image, region: Region) -> tuple[Image.Image, Image.Image, dict, tuple[str, ...]]:
    left, top, right, bottom = region.box
    if not (0 <= left < right <= original.width and 0 <= top < bottom <= original.height):
        raise ValueError("자동 검출된 영역 좌표가 이미지 범위를 벗어났습니다.")
    cropped = original.crop(region.box)
    angle = estimate_skew(cropped)
    corrected = cropped.rotate(angle, Image.Resampling.BICUBIC, expand=True, fillcolor="white") if abs(angle) >= 0.3 else cropped.copy()
    scale = min(3.0, max(1.0, 64 / region.text_height), 2400 / corrected.width, 1600 / corrected.height)
    resized = corrected.resize((max(8, round(corrected.width * scale)), max(8, round(corrected.height * scale))), Image.Resampling.LANCZOS)
    array = np.asarray(resized.convert("RGB"))
    lab = cv2.cvtColor(array, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
    enhanced = Image.fromarray(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB))
    gray = cv2.cvtColor(np.asarray(cropped.convert("RGB")), cv2.COLOR_RGB2GRAY)
    warnings = []
    if region.text_height < 12:
        warnings.append("원본의 글씨가 작습니다. 확대 인식 후에도 빠진 글자는 원본과 비교해 주세요.")
    if cv2.Laplacian(gray, cv2.CV_64F).var() < 20:
        warnings.append("글자 영역이 흐리거나 대비가 낮습니다. 원본에서 사라진 글자는 복원할 수 없습니다.")
    metadata = {"region_method": region.method, "crop_box": region.box,
                "deskew_degrees": angle, "scale": scale, "image_size": resized.size,
                "bbox_coordinate_system": "selected processed image pixels"}
    return resized, enhanced, metadata, tuple(warnings)
