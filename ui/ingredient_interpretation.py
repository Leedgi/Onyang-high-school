"""성분별 근거 중심 해석. 완제품 pH·위험도 예측을 수행하지 않음."""
from ui.chemistry_panel import chemical_info

def interpret(name):
    info = chemical_info(name)
    if not info:
        return ("자료 미확인", "성분별 산·염기 자료가 등록되지 않았습니다.", "검증 필요")
    formula, category, note = info
    if category:
        return (category, note, "등록된 성분별 자료")
    return ("산·염기 미확정", note or "용액 조건에 따라 달라질 수 있습니다.", "검증 필요")

def contextual_notes(name):
    """인체·환경 위해성 판정이 아닌, 관련성을 검토할 항목."""
    key = name.casefold().replace(" ", "")
    uv_names = ("titaniumdioxide", "티타늄디옥사이드", "zincoxide", "징크옥사이드")
    fragrance_names = ("fragrance", "parfum", "향료", "limonene", "리모넨", "linalool", "리날룰")
    if key in {"salicylicacid", "살리실릭애씨드", "살리실산", "glycolicacid", "글라이콜릭애씨드", "글리콜산", "lacticacid", "락틱애씨드", "젖산", "mandelicacid", "만델릭애씨드", "만델산"}:
        return ("산 성분은 사용 농도·완제품 pH·사용 빈도에 따라 피부 자극 가능성이 달라질 수 있습니다. 특히 각질 관리 제품은 사용법과 자외선 노출 관련 안내를 확인하세요.",
                "환경 영향은 성분별 생분해성 및 수생생물 시험자료가 있어야 판단할 수 있습니다.",
                "성분군 기반 주의 설명 (제품 위험 판정 아님)")
    if key in uv_names:
        return ("자외선 차단 등에 사용될 수 있는 성분입니다. 실제 피부 영향은 제형·사용 조건에 따라 다르며 성분명만으로 안전성 등급을 매길 수 없습니다.",
                "수생 환경 영향은 입자 형태·코팅·노출량과 시험 조건에 따라 달라집니다.",
                "성분군 기반 설명 (시험자료 대체 불가)")
    if key in fragrance_names:
        return ("향료 관련 성분은 일부 사람에게 접촉 알레르기 반응을 일으킬 수 있어 개인의 과거 반응과 표시 성분을 확인하는 것이 중요합니다.",
                "환경 영향은 물질별 분해성과 수생 독성 자료가 필요합니다.",
                "성분군 기반 주의 설명 (개인별 진단 아님)")
    return ("이 성분에 대한 개별 인체 유해성 근거가 현재 등록되지 않았습니다. 자료가 없다는 사실은 안전하거나 위험하다는 뜻이 아닙니다.",
            "이 성분에 대한 개별 생분해성·수생독성 자료가 현재 등록되지 않았습니다.",
            "개별 근거 미등록")
