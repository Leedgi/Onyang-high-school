from core.database import IngredientDatabase
from core.models import ClassifiedIngredient, ConfirmedIngredient
from core.normalize import normalize_key
from core.match import find_candidates


def classify(item: ConfirmedIngredient, database: IngredientDatabase) -> ClassifiedIngredient:
    """확정한 이름을 조회하고, 없으면 미등록 원인을 보존해 반환한다."""
    record = database.find(item.name)
    method = "exact" if record and normalize_key(item.name) == normalize_key(record.name) else "alias"
    if record is None:
        match = find_candidates(item.name, database)
        # 확인한 입력의 서식·검증된 별칭만 정리한다. 유사한 이름은 확정하지 않는다.
        if match.status in {"exact", "alias"}:
            record = database.find(match.candidates[0].name)
            method = "normalized" if match.status == "exact" else "alias"
    if record is None:
        return ClassifiedIngredient(
            item, item.name, "확인 필요", "검토 DB에 등록되지 않은 이름입니다.",
            "db_missing", "none",
        )
    return ClassifiedIngredient(
        item, record.name, record.origin, record.reason, record.uncertainty_reason,
        method,
        record.functions, record.source_url, record.checked_on,
        record.detail_origin, record.detail_confidence, record.detail_reason, record.detail_source_url, record.detail_is_estimate,
    )
