import math

from core.models import ClassifiedIngredient, ORIGINS, RatioResult

TOLERANCE = 1e-6


def count_ratio(rows: tuple[ClassifiedIngredient, ...]) -> RatioResult | None:
    if not rows:
        return None
    denominator = len(rows)
    values = {origin: sum(row.origin == origin for row in rows) / denominator * 100 for origin in ORIGINS}
    return RatioResult(values, denominator, "성분명 개수 기준 비율", "%", "count")


def validate_amounts(rows: tuple[ClassifiedIngredient, ...]) -> None:
    """입력된 함량은 계산 모드와 무관하게 검사한다. 0과 미공개를 구분한다."""
    disclosed = [row.confirmed for row in rows if row.confirmed.amount is not None]
    for item in disclosed:
        if isinstance(item.amount, bool) or not isinstance(item.amount, (int, float)):
            raise ValueError(f"{item.name}: 함량은 숫자 또는 미공개여야 합니다.")
        if not math.isfinite(item.amount) or not 0 <= item.amount <= 100:
            raise ValueError(f"{item.name}: 함량은 0~100 사이의 유한한 숫자여야 합니다.")
        if item.unit != "%" or item.basis not in {"mass", "volume"}:
            raise ValueError("함량은 제품 전체 기준의 질량% 또는 부피%만 지원합니다.")
    if len({item.basis for item in disclosed}) > 1:
        raise ValueError("질량 기준과 부피 기준을 섞어 계산할 수 없습니다.")
    if math.fsum(item.amount for item in disclosed) > 100 + TOLERANCE:
        raise ValueError("공개 함량의 합계가 100%를 초과합니다.")


def amount_ratio(rows: tuple[ClassifiedIngredient, ...], mode: str) -> RatioResult | None:
    if mode not in {"count", "partial", "full"}:
        raise ValueError("지원하지 않는 계산 방식입니다.")
    validate_amounts(rows)
    if not rows or mode == "count":
        return None
    known = [row for row in rows if row.confirmed.amount is not None]
    if not known:
        raise ValueError("함량 계산에는 한 개 이상의 공개 함량이 필요합니다.")
    total = math.fsum(row.confirmed.amount for row in known)
    if mode == "full" and (len(known) != len(rows) or abs(total - 100) > TOLERANCE):
        raise ValueError("전체 공개 모드는 모든 성분의 함량과 합계 100%가 필요합니다.")
    if mode == "partial" and len(known) < len(rows) and total >= 100:
        raise ValueError("미공개 성분이 있는데 공개 합계가 100%입니다. 공개 범위를 확인해 주세요.")
    values = {origin: math.fsum(row.confirmed.amount for row in known if row.origin == origin) for origin in ORIGINS}
    values["미공개"] = max(0.0, 100 - total)
    return RatioResult(values, 100, "제품 전체 기준 공개 함량 비율", "%", known[0].confirmed.basis)
