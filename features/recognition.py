"""학생 A의 공개 진입점. 화면과 분석을 import하지 않는다."""
from collections.abc import Callable

from core.database import load_ingredients
from core.image_input import load_image
from core.ingredient_text import split_known_sequence
from core.match import find_candidates, load_match_settings
from core.normalize import clean_ocr_fragment, normalize_text
from core.ocr import OCREngine
from core.scan import scan_ingredients
from shared.contracts import IngredientDraft, ScanOutput


def recognize_photo(data: bytes, filename: str, *, engine: OCREngine,
                    progress: Callable[[str], None] | None = None) -> ScanOutput:
    """사진 검사→자동 영역·보정·OCR→미확정 목록. 잘못된 파일은 ValueError."""
    image = load_image(data, filename)
    return scan_ingredients(image, engine, load_ingredients(), progress=progress)


def prepare_review(text: str) -> tuple[IngredientDraft, ...]:
    """직접 입력·수정한 성분을 대조한다. 사진을 OCR한 결과라고 부르지 않는다."""
    database = load_ingredients()
    settings = load_match_settings()
    drafts = []
    for token in normalize_text(text):
        parts = split_known_sequence(token.name, database)
        _, cleanup = clean_ocr_fragment(token.name)
        for part in parts:
            match = find_candidates(part, database, settings)
            identified = match.status in {"exact", "alias"}
            drafts.append(IngredientDraft(
                raw_text=token.raw_text.strip() if len(parts) == 1 else part,
                name=match.candidates[0].name if identified else match.cleaned_text,
                status=match.status if identified else "needs_review" if match.candidates else "unmatched",
                transformations=tuple(dict.fromkeys((*token.transformations, *cleanup, *match.transformations))),
                candidates=match.candidates, original_fragment=token.raw_text,
            ))
    return tuple(drafts)
