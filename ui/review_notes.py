"""분석된 모든 성분에 대해 산·염기와 주의자료의 범위를 구분해 표시."""
from ui.ingredient_interpretation import interpret

def review_notes(result):
    names = list(dict.fromkeys(row.canonical_name for row in result.rows if row.canonical_name))
    classifications = [(n, *interpret(n)) for n in names]
    supported = [(n, kind) for n, kind, _, _ in classifications if kind not in ("자료 미확인", "산·염기 미확정")]
    ph_lines = ["완제품 pH: 미측정. 성분표만으로 완제품의 pH를 계산하거나 산성·염기성을 판정할 수 없습니다."]
    if supported:
        ph_lines.append("확인된 개별 성분 특성: " + "; ".join(f"{n}({kind})" for n, kind in supported[:25]))
    else:
        ph_lines.append("등록된 산·염기 특성 정보가 있는 성분이 없습니다.")
    ph_lines.append("이 결과는 제품의 산성도·자극성 판정이 아닙니다.")
    caution_records = [r for group in result.cautions.values() for r in group]
    human_records = [r for r in caution_records if r.reason.startswith("[인체")]
    env_records = [r for r in caution_records if r.reason.startswith("[환경")]
    human = ("개별 주의 자료가 연결된 성분: " + ", ".join(dict.fromkeys(r.name for r in human_records)) + ". " if human_records else "") + "아래 성분별 설명은 농도·사용 부위·노출 조건에 따른 검토사항이며 제품 전체의 위험도는 계산하지 않습니다."
    environment = ("개별 환경 자료가 연결된 성분: " + ", ".join(dict.fromkeys(r.name for r in env_records)) + ". " if env_records else "") + "환경 영향은 생분해성·수생 독성·실제 배출량 등 자료가 필요하며 식물성·합성이라는 유래만으로 판단할 수 없습니다."
    return (("산성도(pH) · 확인 불가", " ".join(ph_lines)),
            ("인체 영향 · 성분별 주의 있음" if human_records else "인체 영향 · 판단 보류", human),
            ("환경 영향 · 성분별 시험자료 있음" if env_records else "환경 영향 · 자료 부족", environment))
