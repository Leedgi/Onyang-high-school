"""불확실한 성분의 실제 픽셀 영역만 AI로 다시 읽는다. 원문을 덮어쓰거나 이름을 확정하지 않는다."""
from dataclasses import replace, asdict
import math
import re
import unicodedata

from PIL import Image
from rapidfuzz.distance import Levenshtein

from core.ingredient_text import ingredient_drafts
from core.normalize import normalize_key, search_view


def _units(text: str) -> float:
    return sum(0.3 if char.isspace() else 1.0 if unicodedata.east_asian_width(char) in {"W", "F"} else 0.55 for char in text)


def word_image(image, ocr, text):
    """OCR 줄 좌표와 문자 위치로 단어 범위를 근사한다. 줄을 넘긴 이름은 실제 조각을 이어 붙인다."""
    blocks = {block.source_index: block for block in ocr.blocks}
    compact, mapping, lines = [], [], []
    for i, line in enumerate(ocr.lines):
        content, key, positions = search_view(line.raw_text)
        lines.append(content)
        compact.extend(key)
        mapping.extend((i, j) for j in positions)
    query = normalize_key(text)
    start = "".join(compact).find(query)
    if start < 0:
        return None
    groups = {}
    for i, j in mapping[start:start + len(query)]:
        groups.setdefault(i, []).append(j)
    pieces, boxes = [], []
    for i, positions in groups.items():
        line = ocr.lines[i]
        points = [p for index in line.source_indices if index in blocks for p in blocks[index].bbox]
        if not points:
            return None
        xs, ys = zip(*points)
        x, y, right, bottom = min(xs), min(ys), max(xs), max(ys)
        content = lines[i]
        # 단일 행 엔진의 실제 단어 상자가 있으면 전체 줄 폭의 비례 추정보다 우선한다.
        precise, covered, cursor = [], set(), 0
        for index in line.source_indices:
            if index not in blocks:
                continue
            block = blocks[index]
            part = unicodedata.normalize("NFKC", block.raw_text)
            at = content.find(part, cursor)
            if at < 0:
                continue
            cursor = at + len(part)
            begin, end = max(at, min(positions)), min(cursor, max(positions) + 1)
            if begin >= end:
                continue
            bx, by = min(p[0] for p in block.bbox), min(p[1] for p in block.bbox)
            br, bb = max(p[0] for p in block.bbox), max(p[1] for p in block.bbox)
            units = max(1, _units(part))
            precise.append((bx + (br-bx)*_units(part[:begin-at])/units, by,
                            bx + (br-bx)*_units(part[:end-at])/units, bb))
            covered.update(range(begin,end))
        if precise and all(j in covered or content[j].isspace() for j in positions):
            x, y, right, bottom = (min(b[0] for b in precise), min(b[1] for b in precise),
                                   max(b[2] for b in precise), max(b[3] for b in precise))
            content = content[min(positions):max(positions)+1]
            positions = list(range(len(content)))
        total = max(1, _units(content))
        pad = max(3, (bottom - y) * 0.18)
        box = (max(0, math.floor(x + (right - x) * _units(content[:min(positions)]) / total - pad)),
               max(0, math.floor(y - pad)),
               min(image.width, math.ceil(x + (right - x) * _units(content[:max(positions) + 1]) / total + pad)),
               min(image.height, math.ceil(bottom + pad)))
        if box[2] <= box[0] or box[3] <= box[1]:
            return None
        boxes.append(box)
        pieces.append(image.crop(box))
    if not pieces:
        return None
    height = 96
    resized = [piece.resize((max(4, round(piece.width * height / piece.height)), height), Image.Resampling.LANCZOS) for piece in pieces]
    patch = Image.new("RGB", (sum(piece.width for piece in resized) + 8 * (len(pieces) - 1), height), "white")
    cursor = 0
    for piece in resized:
        patch.paste(piece, (cursor, 0))
        cursor += piece.width + 8
    patch.thumbnail((1800, 160))
    return patch, tuple(boxes)


def refine_words(image, ocr, drafts, engine, database, progress, limit=12):
    replacements, passes = {}, []
    candidates = [(i, draft) for i, draft in enumerate(drafts)
                  if draft.status in {"needs_review", "unmatched"} and 3 <= len(normalize_key(draft.raw_text)) <= 120]
    candidates.sort(key=lambda item: -(item[1].candidates[0].score if item[1].candidates else 0))
    for i, draft in candidates[:limit]:
        found = word_image(image, ocr, draft.raw_text)
        if found is None:
            continue
        patch, boxes = found
        progress(f"불확실한 성분 영역을 AI로 다시 읽고 있습니다 · {len(passes) + 1}/{min(limit, len(candidates))}")
        line_reader = getattr(engine, "recognize_line", None)
        reread = line_reader(patch) if callable(line_reader) else engine.recognize(patch, "rows", accurate=True)
        proposed = ingredient_drafts(reread, database) if reread.status == "ok" else ()
        score = sum(block.confidence for block in reread.blocks) / max(1, len(reread.blocks))
        query = normalize_key(draft.raw_text)
        target = "".join(normalize_key(item.raw_text) for item in proposed)
        allow = (
            bool(proposed) and score >= 0.55
            and all(item.status in {"exact", "alias"} for item in proposed)
            and re.findall(r"\d+", query) == re.findall(r"\d+", target)
            and Levenshtein.distance(query, target) <= max(2, int(len(query) * 0.2))
        )
        independent = None
        consensus = False
        if not allow and callable(line_reader):
            independent = engine.recognize(patch, "rows", accurate=False)
            independent_drafts = ingredient_drafts(independent, database) if independent.status == "ok" else ()
            independent_score = sum(b.confidence for b in independent.blocks) / max(1,len(independent.blocks))
            def supported(items):
                if len(items) != 1 or not items[0].candidates:
                    return None
                item = items[0]; candidate = item.candidates[0]
                if candidate.score < 85 or (len(item.candidates)>1 and candidate.score-item.candidates[1].score < 8):
                    return None
                record = database.find(candidate.name)
                if not record:
                    return None
                if re.findall(r"\d+", normalize_key(item.raw_text)) != re.findall(r"\d+", normalize_key(candidate.matched_name)):
                    return None
                return candidate
            left, right = supported(proposed), supported(independent_drafts)
            consensus = bool(left and right and left.name == right.name and score >= .55 and independent_score >= .35
                             and re.findall(r"\d+",query) == re.findall(r"\d+", normalize_key(left.matched_name))
                             and Levenshtein.distance(query,normalize_key(left.matched_name)) <= max(2,int(len(query)*.12)))
            if consensus:
                proposed = (replace(proposed[0],name=left.name),)
                allow = True
        if allow:
            replacements[i] = tuple(replace(item, raw_text=draft.raw_text, status="ai_reread_proposed",
                                           source_indices=draft.source_indices, original_fragment=draft.original_fragment or draft.raw_text,
                                           transformations=(*draft.transformations, "두 로컬 OCR의 픽셀 재인식 후보 일치·미확정" if consensus else "실제 단어 픽셀 AI 재인식 기반 제안·미확정")) for item in proposed)
        passes.append({"stage": "word_reread", "draft_index": i, "source_text": draft.raw_text,
                       "crop_boxes_in_selected_image": boxes, "image_size": patch.size,
                       "ocr": asdict(reread), "applied_as_unconfirmed_proposal": allow,
                       "proposed_names": [item.name for item in proposed],
                       "independent_ocr": asdict(independent) if independent else None, "two_engine_consensus": consensus})
    result = tuple(item for i, draft in enumerate(drafts) for item in replacements.get(i, (draft,)))
    return result, tuple(passes)
