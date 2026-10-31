"""사용자 확정 뒤 실행하는 통합 처리. UI를 직접 변경하지 않는다."""
from core.caution import lookup_cautions
from core.classify import classify
from core.database import IngredientDatabase
from core.models import AnalysisResult, CautionRecord, ConfirmedIngredient
from core.normalize import normalize_key
from core.ratio import amount_ratio, count_ratio, validate_amounts, detail_count_ratio


def analyze(
    confirmed: list[ConfirmedIngredient], database: IngredientDatabase,
    cautions: list[CautionRecord], mode: str = "count",
) -> AnalysisResult:
    classified = []
    duplicates = []
    seen = {}
    for item in confirmed:
        if not item.name.strip():
            raise ValueError("빈 성분명은 확정할 수 없습니다. 행을 삭제하거나 이름을 입력해 주세요.")
        row = classify(item, database)
        validate_amounts((row,))
        key = normalize_key(row.canonical_name)
        if key in seen:
            previous = seen[key].confirmed
            if (previous.amount, previous.unit, previous.basis) != (item.amount, item.unit, item.basis):
                raise ValueError(f"{item.name}: 중복 이름의 함량 정보가 다릅니다. 하나로 정리해 주세요.")
            duplicates.append(item.name)
        else:
            seen[key] = row
            classified.append(row)
    rows = tuple(classified)
    amounts = amount_ratio(rows, mode)
    return AnalysisResult(
        "complete" if rows else "no_data", database.dataset_kind, tuple(confirmed), rows,
        tuple(duplicates), count_ratio(rows), amounts, lookup_cautions(rows, cautions),
        detail_count_ratio(rows) if database.detail_origin_counts is not None else None,
    )
