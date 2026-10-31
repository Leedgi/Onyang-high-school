"""자동 영역 탐색 → 보정 → 두 경로 AI 재인식 → 성분 단위 초안. 외부 API를 호출하지 않는다."""
from dataclasses import dataclass, asdict, replace
from collections.abc import Callable
from statistics import mean, median

from PIL import Image
import cv2
import numpy as np

from core.auto_preprocess import locate_region, prepare_region, curved_text_variant, rectified_text_rows
from core.database import IngredientDatabase
from core.ingredient_text import ingredient_drafts
from core.models import IngredientScan, OCRResult, OCRLine
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
    return confidence * 0.4 + exact * 0.6, drafts, exact



def _read_rows(rows, engine):
    canvas = Image.new("RGB", (max(row.width for row in rows), sum(row.height + 12 for row in rows)), "white")
    blocks, lines, offsets = [], [], []
    cursor = 0
    for row in rows:
        result = engine.recognize_line(row)
        if result.status != "ok" or not result.blocks:
            return canvas, result, offsets
        indices = []
        for block in result.blocks:
            index = len(blocks)
            blocks.append(replace(block, source_index=index, bbox=tuple((x, y + cursor) for x, y in block.bbox)))
            indices.append(index)
        lines.append(OCRLine(result.raw_text, tuple(indices)))
        canvas.paste(row, (0, cursor))
        offsets.append(cursor)
        cursor += row.height + 12
    return canvas, OCRResult("ok", "\n".join(line.raw_text for line in lines), tuple(blocks), tuple(lines)), offsets


def _known_support(drafts):
    known = {}
    for draft in drafts:
        if draft.candidates and draft.status in {"exact", "alias", "correction_proposed"}:
            name = draft.candidates[0].name
            known[name] = max(known.get(name, 0), 1 if draft.status in {"exact", "alias"} else .6)
    return sum(known.values())


def scan_ingredients(image: Image.Image, engine: OCREngine, database: IngredientDatabase,
                     progress: Callable[[str], None] | None = None) -> ScanOutput:
    if getattr(engine, "neural_enabled", False):
        return _scan_neural(image, engine, database, progress)
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
    weak = (best is None or best[4].method == "not_found"
            or sum(d.status in {"exact", "alias"} for d in ingredient_drafts(best[3], database)) < 3
            or (best[4].method != "heading" and best[0] < 13))
    if weak:
        for fallback_angle in (0, 180, 90, 270):
            report(f"불명확한 사진 방향을 인쇄 글자 엔진으로 다시 비교하고 있습니다 · {fallback_angle}°")
            fallback_image = image.rotate(fallback_angle, expand=True)
            probe = fallback_image.copy()
            probe.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
            precise = engine.recognize(probe, "rows", accurate=True)
            if precise.status in {"model_error", "dependency_error"}:
                return ScanOutput(IngredientScan(precise.status, precise, message=precise.message), image.copy())
            if precise.status != "ok":
                continue
            if probe.size != fallback_image.size:
                sx, sy = fallback_image.width/probe.width, fallback_image.height/probe.height
                precise = replace(precise, blocks=tuple(replace(b, bbox=tuple((x*sx,y*sy) for x,y in b.bbox)) for b in precise.blocks))
            refined_region = locate_region(precise, fallback_image.size, database)
            _, refined_drafts, fraction = _quality(precise, database)
            count = sum(d.status in {"exact", "alias"} for d in refined_drafts)
            accepted = refined_region.method == "heading" or (count >= 3 and fraction >= .35)
            score = ((6 if refined_region.method == "heading" else 3) + min(count,30) + fraction*4
                     + (mean(b.confidence for b in precise.blocks) if precise.blocks else 0.)*2
                     + min(len(refined_drafts),40)*.05)
            orientation_passes.append({"stage":"orientation_refine","rotation":fallback_angle,
                                       "region_method":refined_region.method,"eligible":accepted,
                                       "selection_score":score,"ocr":asdict(precise)})
            if accepted and refined_region.method != "not_found" and (best is None or score>best[0]):
                best=(score,fallback_angle,fallback_image,precise,refined_region)
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
    metadata.update({"pipeline_version": 6, "recognizer_model_revision": LSTM_REVISION})
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
    row_passes = []
    primary = max(successful, key=lambda item: item[3]) if successful else alternatives[0]
    if callable(getattr(engine, "recognize_line", None)) and (not successful or primary[5] < .98):
        for theta in (0.0, .95):
            label = f"줄별 곡면 보정 {theta:.2f}"
            report(f"휜 인쇄 줄을 각각 펴서 다시 읽고 있습니다 · {theta:.2f}")
            try:
                rows, row_metadata = rectified_text_rows(primary[1], region.text_height * metadata["scale"], theta)
                canvas, row_ocr, offsets = _read_rows(rows, engine)
                score, row_drafts, fraction = _quality(row_ocr, database) if row_ocr.status == "ok" else (0., (), 0.)
                eligible = (row_ocr.status == "ok" and bool(row_drafts)
                            and len(normalize_key(row_ocr.raw_text)) >= .85 * len(normalize_key(primary[2].raw_text))
                            and _known_support(row_drafts) >= _known_support(primary[4]))
                row_passes.append({"stage": "tracked_rows", "variant": label, "processing": row_metadata,
                                   "row_offsets_in_selected_image": offsets, "eligible": eligible,
                                   "ocr": asdict(row_ocr), "image_size": canvas.size})
                if eligible:
                    alternatives.append((label, canvas, row_ocr, score, row_drafts, fraction))
            except (ValueError, OSError, cv2.error, np.linalg.LinAlgError) as exc:
                row_passes.append({"stage": "tracked_rows", "variant": label, "eligible": False,
                                   "message": str(exc)})
        successful = [item for item in alternatives if item[2].status == "ok" and item[4]]
    if not successful:
        failed = next((item[2] for item in alternatives if item[2].status not in {"ok", "empty"}), None)
        ocr = failed or alternatives[0][2]
        return ScanOutput(IngredientScan(ocr.status if failed else "empty", ocr, processing=metadata,
                                        warnings=warnings, message=ocr.message or "전성분 영역에서 목록을 읽지 못했습니다. 다시 시도하거나 직접 입력해 주세요."), normal)
    initial_longest = max(len(normalize_key(item[2].raw_text)) for item in successful)
    best_initial = primary if primary[2].status == "ok" and primary[4] else max(successful, key=lambda item: item[3])
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
    longest = max(len(normalize_key(item[2].raw_text)) for item in alternatives if item[2].status == "ok")
    most_known = max(1., max(_known_support(item[4]) for item in alternatives))
    # 한두 개 쉬운 이름만 읽은 경로가 긴 목록을 읽은 경로를 부당하게 이기지 않게 한다.
    alternatives = [(label, candidate_image, result,
                     score * 0.2 + 0.15 * len(normalize_key(result.raw_text)) / max(1, longest) + 0.65 * _known_support(drafts) / most_known, drafts, fraction)
                    for label, candidate_image, result, score, drafts, fraction in alternatives]
    successful = [item for item in alternatives if item[2].status == "ok" and item[4]]
    chosen = max(successful, key=lambda item: item[3])
    original_paths = [item for item in successful if not item[0].startswith("줄별 곡면")]
    if original_paths and chosen[0].startswith("줄별 곡면"):
        reference = max(original_paths, key=lambda item: item[3])
        if _known_support(chosen[4]) <= _known_support(reference[4]) + .1 and chosen[3] < reference[3] + .015:
            chosen = reference
    label, selected_image, ocr, quality, drafts, coverage = chosen
    if any(item[2].status not in {"ok", "empty"} for item in alternatives):
        warnings = (*warnings, "일부 재인식 과정이 실패해 성공한 경로만 사용했습니다.")
    metadata["selected_variant"] = label
    metadata["prepared_region_image_size"] = normal.size
    metadata["image_size"] = selected_image.size
    if label.startswith("줄별 곡면"):
        selected_rows = next(item for item in row_passes if item["variant"] == label)
        metadata["row_rectification"] = {**selected_rows["processing"], "row_offsets": selected_rows["row_offsets_in_selected_image"],
                                         "source_coordinate_system": "unrectified prepared region pixels"}
    metadata["selection_note"] = "OCR 점수와 사전 완전 일치를 참고한 경로 선택이며 정답률이 아닙니다."
    passes = (*orientation_passes, *row_passes, *({"variant": variant, "image_size": variant_image.size, "ocr": asdict(result), "selection_score": score,
                                   "dictionary_exact_fraction": fraction, "known_name_support": _known_support(items)} for variant, variant_image, result, score, items, fraction in alternatives))
    report("줄 사이에서 끊긴 이름과 누락 구분자를 정리해 확인할 목록을 만들고 있습니다")
    drafts, word_passes = refine_words(selected_image, ocr, drafts, engine, database, report)
    metadata["word_reread_count"] = len(word_passes)
    passes = (*passes, *word_passes)
    return ScanOutput(IngredientScan("ok", ocr, drafts, metadata, tuple(passes), warnings), selected_image)



def _preferred_label(ocr):
    """한·영 병기가 있으면 한글 전성분 한 목록만 쓴다. 같은 이름을 두 번 세지 않는다."""
    from core.ingredient_text import heading_span, section_end_span
    import re
    korean = next((i for i, line in enumerate(ocr.lines)
                   if heading_span(line.raw_text) and re.search(r"전\s*성", line.raw_text)), None)
    if korean is None:
        return ocr
    lines = []
    for line in ocr.lines[korean:]:
        if lines and (section_end_span(line.raw_text) or heading_span(line.raw_text)):
            break
        lines.append(line)
    return replace(ocr, raw_text="\n".join(line.raw_text for line in lines), lines=tuple(lines))


def _neural_score(ocr, database):
    selected = _preferred_label(ocr)
    quality, drafts, fraction = _quality(selected, database)
    from core.ingredient_text import heading_span
    heading = any(heading_span(line.raw_text) for line in selected.lines)
    return _known_support(drafts) + min(2., len(drafts) * .02) + quality * 2 + (3 if heading else 0), drafts, fraction


def _scan_neural(image, engine, database, progress):
    report = progress or (lambda _: None)
    passes, choices = [], []
    for angle in (0, 180, 90, 270):
        report(f"한국어 글자 줄과 사진 방향을 자동 비교하고 있습니다 · {angle}°")
        rotated = image.rotate(angle, expand=True)
        ocr = engine.recognize_neural(rotated, limit=1280)
        if ocr.status in {"dependency_error", "model_error"}:
            return ScanOutput(IngredientScan(ocr.status, ocr, message=ocr.message), image.copy())
        score, drafts, fraction = _neural_score(ocr, database)
        passes.append({"stage": "neural_orientation", "rotation": angle, "selection_score": score, "ocr": asdict(ocr)})
        choices.append((score, angle, rotated, ocr))
    _, rotation, upright, coarse = max(choices, key=lambda item: item[0])
    # 긴 글자 줄의 방향을 사용한다. 포장지 테두리나 배경 선으로 기울기를 정하지 않는다.
    angles = []
    for block in coarse.blocks:
        a, b, c, d = block.bbox
        width = np.linalg.norm(np.array(a)-b)
        height = np.linalg.norm(np.array(a)-d)
        if width > height * 4:
            angle = np.degrees(np.arctan2(b[1]-a[1], b[0]-a[0]))
            if abs(angle) <= 40:
                angles.append(float(angle))
    deskew = float(median(angles)) if len(angles) >= 3 else 0.
    if abs(deskew) >= 3.:
        report("검출한 글자 줄을 기준으로 사진의 기울기를 바로잡고 있습니다")
        upright = upright.rotate(deskew, Image.Resampling.BICUBIC, expand=True, fillcolor="white")
        coarse = engine.recognize_neural(upright, limit=1600)
        passes.append({"stage": "neural_deskew", "degrees": deskew, "ocr": asdict(coarse)})
    # 성분 영역을 고를 때 한글 목록과 다른 언어 목록을 이어 붙이지 않는다.
    coarse = _preferred_label(coarse)
    region = locate_region(coarse, upright.size, database)
    if region.method == "not_found":
        status = "empty" if not coarse.blocks else "region_not_found"
        message = "전성분 영역을 찾지 못했습니다. 성분표를 가까이 촬영하거나 성분명을 직접 입력해 주세요."
        return ScanOutput(IngredientScan(status, coarse, passes=tuple(passes), message=message), upright)
    selected_image = upright.crop(region.box)
    variants = []
    for label, dewarp in (("원근 보정 줄 인식", False), ("검출 윤곽 곡면 보정", True)):
        report(f"원본 해상도로 성분표를 읽고 있습니다 · {label}")
        ocr = _preferred_label(engine.recognize_neural(selected_image, limit=1600, dewarp=dewarp))
        score, drafts, fraction = _neural_score(ocr, database)
        variants.append((score, label, ocr, drafts, fraction))
        passes.append({"stage": "neural_region", "variant": label, "selection_score": score, "ocr": asdict(ocr)})
    score, label, ocr, drafts, fraction = max(variants, key=lambda item: item[0])
    if not drafts:
        return ScanOutput(IngredientScan(ocr.status if ocr.status != "ok" else "empty", ocr,
                                        passes=tuple(passes), message=ocr.message or "성분명을 읽지 못했습니다."), selected_image)
    processing = {"pipeline_version": 7, "recognizer_model_revision": "ppocr-v5-korean-1",
                  "locator_engine": "PP-OCRv5 DB", "recognizer_engine": "PP-OCRv5 Korean / ONNX CPU",
                  "rotation": rotation, "deskew_degrees": deskew, "rotated_size": upright.size,
                  "region_method": region.method, "crop_box": region.box, "scale": 1.,
                  "image_size": selected_image.size, "selected_variant": label,
                  "bbox_coordinate_system": "selected processed image pixels",
                  "selection_note": "사진 픽셀·문자 사전을 이용한 경로 선택이며 정답률이 아닙니다."}
    return ScanOutput(IngredientScan("ok", ocr, drafts, processing, tuple(passes)), selected_image)
