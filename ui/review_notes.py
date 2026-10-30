"""확정 결과에 붙이는 평가 한계 안내. 성분의 위해성이나 pH를 새로 분류하지 않는다."""
from core.models import AnalysisResult


def review_notes(result: AnalysisResult) -> tuple[tuple[str, str], ...]:
    buffering = [r.canonical_name for r in result.rows if "BUFFERING" in r.functions]
    ph = "성분명과 배열 순서만으로 완제품의 pH를 계산하거나 산성·염기성을 판정할 수 없습니다. 제조사가 공개한 완제품 pH 또는 측정값을 확인해 주세요."
    if buffering:
        ph += " 기존 DB에 완충(BUFFERING) 기능이 기록된 성분: " + ", ".join(buffering) + ". 이 표기는 완제품의 pH나 자극성을 뜻하지 않습니다."
    return (
        ("산성도(pH) · 확인 불가", ph),
        ("인체 영향 · 판단 보류", "함량, 제품 종류, 씻어내는지 여부, 사용 부위와 개인의 알레르기 정보가 없어 제품의 자극성·안전성을 판정하지 않습니다. 성분별 주의 자료가 표시되더라도 적용 조건을 확인해야 하며, 자료가 없는 것을 안전함으로 해석하지 마세요."),
        ("환경 영향 · 자료 부족", "성분명이나 석유계·식물성 분류만으로 생분해성, 환경 잔류성, 수생생물 영향을 확정할 수 없습니다. 물질별 시험자료와 배출·노출 조건이 필요합니다. 현재 자료가 없는 성분을 ‘잘 분해됨’ 또는 ‘환경에 안전함’으로 표시하지 않습니다."),
    )
