from core.database import IngredientDatabase
from core.models import ClassifiedIngredient, ConfirmedIngredient
from core.normalize import normalize_key
from core.match import find_candidates
from dataclasses import replace
from rapidfuzz import process
from rapidfuzz.fuzz import ratio


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


def origin_references(database):
    """DB의 비추정 분류만 참조한다. 사용자 입력/사진을 캐시하지 않는다."""
    return {normalize_key(name): record for record in sorted(database.records, key=lambda r: r.name)
            if record.detail_origin and record.detail_origin != "확인 필요" and not record.detail_is_estimate
            for name in (record.name, *record.aliases)}


def estimate_origin(row, references):
    """등록 이름의 유래만 이름 유사도로 추정. 원래 근거/4분류는 보존한다."""
    if row.detail_origin not in {"", "확인 필요"} or row.uncertainty_reason == "db_missing":
        return row
    query = normalize_key(row.canonical_name)
    if len(query) < 4:
        return row
    closest = process.extractOne(query, references.keys(), scorer=ratio, score_cutoff=75)
    if closest is None:
        return row
    key, score, _ = closest
    reference = references[key]
    return replace(row, detail_origin=reference.detail_origin, detail_is_estimate=True,
                   detail_confidence="유사 성분명 기반 자동 추정(제조 원료 미확인)",
                   detail_reason=f"{reference.name}의 분류를 참고한 추정입니다. 이름 유사도 {score:.1f}점은 정답 확률이 아니며 같은 물질/공급원이라는 뜻이 아닙니다.",
                   detail_source_url=reference.detail_source_url or reference.source_url)
