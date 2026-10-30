"""자동 영역 탐색 → 보정 → 두 경로 AI 재인식 → 성분 단위 초안. 외부 API를 호출하지 않는다."""
from dataclasses import dataclass, asdict, replace
from collections.abc import Callable
from statistics import mean

from PIL import Image
import cv2
import numpy as np

from core.auto_preprocess import locate_region, prepare_region, curved_text_variant
from core.database import IngredientDatabase
from core.ingredient_text import ingredient_drafts
from core.models import IngredientScan, OCRResult
from core.normalize import normalize_key
from core.ocr import OCREngine
from core.word_refine import refine_words
from core.lstm_ocr import REVISION as LSTM_REVISION


@dataclass(frozen=True)
class ScanOutput:
    result: IngredientScan
    image: Image.Image


def _quality(ocr: OCRResult, database: IngredientDatabase) -> tuple[float, tuple, float]:
    drafts = ingredient_drafts(ocr, database)
    exact = sum(draft.status in {"exact", "alias"} for draft in drafts) / max(1, len(drafts))
    confidence = mean(block.confidence for block in ocr.blocks) if ocr.blocks else 0.0
    return confidence * 0.65 + exact * 0.35, drafts, exact


def scan_ingredients(image: Image.Image, engine: OCREngine, database: IngredientDatabase,
                     progress: Callable[[str], None] | None = None) -> ScanOutput:
    report = progress or (lambda message: None)
    best = None
    orientation_passes = []
    for angle in (0, 180, 90, 270):
        report(f"AI로 글자와 전성분 표지를 찾고 있습니다 · 방향 {angle}°")
        rotated = image.rotate(angle, expand=True)
        probe = rotated.copy()
        probe.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        coarse = engine.recognize(probe, "rows")
        # 영역 탐색은 축소 영상, 실제 재인식은 원본 해상도로 자른 영상에서 한다.
        if probe.size != rotated.size:
            sx, sy = rotated.width / probe.width, rotated.height / probe.height
            coarse = replace(coarse, blocks=tuple(replace(block, bbox=tuple((x * sx, y * sy) for x, y in block.bbox)) for block in coarse.blocks))
        if coarse.status not in {"ok", "empty"}:
            orientation_passes.append({"rotation": angle, "image_size": rotated.size, "region_method": "failed", "ocr": asdict(coarse)})
            if coarse.status in {"model_error", "dependency_error"}:
                return ScanOutput(IngredientScan(coarse.status, coarse, message=coarse.message), image.copy())
            continue
        region = locate_region(coarse, rotated.size, database)
        confidence = mean(block.confidence for block in coarse.blocks) if coarse.blocks else 0.0
        _, coarse_drafts, coarse_coverage = _quality(coarse, database)
        exact_count = sum(d.status in {"exact", "alias"} for d in coarse_drafts)
        score = ({"heading": 6, "dictionary": 3}.get(region.method, 0)
                 + min(exact_count, 30) + coarse_coverage * 4 + confidence * 2
                 + min(len(coarse_drafts), 40) * .05)
        if region.method == "not_found":
            score -= 100
        orientation_passes.append({"rotation": angle, "image_size": rotated.size, "region_method": region.method, "selection_score": score, "ocr": asdict(coarse)})
        if best is None or score > best[0]:
            best = (score, angle, rotated, coarse, region)
    if best is None:
        first = orientation_passes[0]["ocr"]
        ocr = OCRResult(first["status"], message=first.get("message", "방향별 인식에 실패했습니다."))
        return ScanOutput(IngredientScan(ocr.status, ocr, passes=tuple(orientation_passes), message=ocr.message), image.copy())
    _, angle, rotated, coarse, region = best
    if region.method == "not_found":
        status = "empty" if all(not item["ocr"]["blocks"] for item in orientation_passes) else "region_not_found"
        message = "인식된 글자가 없습니다." if status == "empty" else "전성분 영역을 확인하지 못했습니다. 사진의 글자를 성분으로 임의 확정하지 않습니다."
        return ScanOutput(IngredientScan(status, coarse, processing={"rotation": angle, "region_method": region.method},
                                        passes=tuple(orientation_passes), message=message), rotated)
    report("전성분 영역을 자동으로 자르고 기울기·크기·조명을 보정하고 있습니다")
    try:
        normal, enhanced, metadata, warnings = prepare_region(rotated, region)
    except (ValueError, OSError, cv2.error):
        message = "자동 사진 보정에 실패했습니다. 사진을 다시 선택해 시도하거나 성분명을 직접 입력해 주세요."
        return ScanOutput(IngredientScan("execution_error", coarse, message=message), rotated)
    metadata.update({"rotation": angle, "rotated_size": rotated.size})
    metadata.update({"locator_engine": "EasyOCR / CRAFT", "recognizer_engine": "Tesseract LSTM / tessdata_best"})
    metadata.update({"pipeline_version": 5, "recognizer_model_revision": LSTM_REVISION})
    alternatives = []
    for label, candidate_image in (("확대·기울기 보정", normal), ("국소 조명 보정", enhanced)):
        report(f"성분 영역을 AI로 다시 읽고 있습니다 · {label}")
        ocr = engine.recognize(candidate_image, "rows", accurate=True)
        if ocr.status not in {"ok", "empty"}:
            alternatives.append((label, candidate_image, ocr, 0.0, (), 0.0))
        else:
            quality, drafts, coverage = _quality(ocr, database)
            alternatives.append((label, candidate_image, ocr, quality, drafts, coverage))
    successful = [item for item in alternatives if item[2].status == "ok" and item[4]]
    if not successful:
        failed = next((item[2] for item in alternatives if item[2].status not in {"ok", "empty"}), None)
        ocr = failed or alternatives[0][2]
        return ScanOutput(IngredientScan(ocr.status if failed else "empty", ocr, processing=metadata,
                                        warnings=warnings, message=ocr.message or "전성분 영역에서 목록을 읽지 못했습니다. 다시 시도하거나 직접 입력해 주세요."), normal)
    initial_longest = max(len(normalize_key(item[2].raw_text)) for item in successful)
    best_initial = max(successful, key=lambda item: item[3] * .8 + .2 * len(normalize_key(item[2].raw_text)) / max(1, initial_longest))
    if best_initial[5] < .92:
        report("곡면으로 눌리거나 휜 글자를 제한된 대안 경로로 다시 읽고 있습니다")
        try:
            candidate, curve_metadata = curved_text_variant(best_initial[1], region.text_height * metadata["scale"])
            curve_ocr = engine.recognize(candidate, "rows", accurate=True)
            if curve_ocr.status in {"ok", "empty"}:
                score, curve_drafts, fraction = _quality(curve_ocr, database)
            else:
                score, curve_drafts, fraction = 0., (), 0.
            # 짧은 일부만 읽거나 사전 일치가 줄어든 대안은 원래 경로를 대체하지 않는다.
            eligible = (curve_ocr.status == "ok" and curve_drafts
                        and len(normalize_key(curve_ocr.raw_text)) >= .8 * len(normalize_key(best_initial[2].raw_text))
                        and fraction >= best_initial[5] and score > best_initial[3] + .015)
            metadata["curved_alternative"] = {**curve_metadata, "eligible": bool(eligible), "score": score, "coverage": fraction, "baseline_score": best_initial[3], "baseline_coverage": best_initial[5]}
            if eligible:
                alternatives.append(("곡면 가설 보정", candidate, curve_ocr, score, curve_drafts, fraction))
        except (ValueError, OSError, cv2.error, np.linalg.LinAlgError):
            warnings = (*warnings, "곡면 대안 보정을 적용하지 못해 원래 보정 경로를 유지했습니다.")
    longest = max(len(normalize_key(item[2].raw_text)) for item in successful)
    # 한두 개 쉬운 이름만 읽은 경로가 긴 목록을 읽은 경로를 부당하게 이기지 않게 한다.
    alternatives = [(label, candidate_image, result,
                     score * 0.8 + 0.2 * len(normalize_key(result.raw_text)) / max(1, longest), drafts, fraction)
                    for label, candidate_image, result, score, drafts, fraction in alternatives]
    successful = [item for item in alternatives if item[2].status == "ok" and item[4]]
    chosen = max(successful, key=lambda item: item[3])
    label, selected_image, ocr, quality, drafts, coverage = chosen
    if any(item[2].status not in {"ok", "empty"} for item in alternatives):
        warnings = (*warnings, "일부 재인식 과정이 실패해 성공한 경로만 사용했습니다.")
    metadata["selected_variant"] = label
    metadata["selection_note"] = "OCR 점수와 사전 완전 일치를 참고한 경로 선택이며 정답률이 아닙니다."
    passes = (*orientation_passes, *({"variant": variant, "image_size": variant_image.size, "ocr": asdict(result), "selection_score": score,
                                   "dictionary_exact_fraction": fraction} for variant, variant_image, result, score, _, fraction in alternatives))
    report("줄 사이에서 끊긴 이름과 누락 구분자를 정리해 확인할 목록을 만들고 있습니다")
    drafts, word_passes = refine_words(selected_image, ocr, drafts, engine, database, report)
    metadata["word_reread_count"] = len(word_passes)
    passes = (*passes, *word_passes)
    if any(item["ocr"]["status"] not in {"ok", "empty"} for item in word_passes):
        warnings = (*warnings, "일부 단어 재인식이 실패한 항목은 원문과 확인 필요 상태를 유지했습니다.")
    return ScanOutput(IngredientScan("ok", ocr, drafts, metadata, tuple(passes), warnings), selected_image)
