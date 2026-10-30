"""v1 주의 레코드를 조건·출처와 함께 표시한다. 위해성 등급을 새로 계산하지 않는다."""
import streamlit as st


def render_cautions(result) -> None:
    records = [record for group in result.cautions.values() for record in group]
    groups = (
        ("인체·사용상 주의", [r for r in records if r.reason.startswith("[인체")]),
        ("환경·생분해성 시험 자료", [r for r in records if r.reason.startswith("[환경")]),
        ("그 밖의 등록 주의", [r for r in records if not r.reason.startswith(("[인체", "[환경"))]),
    )
    for heading, rows in groups:
        if not rows:
            continue
        st.subheader(heading)
        for record in rows:
            with st.container(border=True):
                st.markdown(f"**{record.name}**")
                st.write(record.reason)
                st.write(record.restriction)
                st.write(record.use_condition)
                st.caption(f"자료 확인일: {record.checked_on} · {record.country}")
                with st.expander("제품·농도 조건과 원문 근거"):
                    st.write("적용 제품: " + record.product_type)
                    st.write("농도·판단 한계: " + record.concentration_condition)
                    st.link_button(f"{record.name} 원문 근거", record.source_url)
    if not records:
        st.info("주의 등급 · 자료 부족\n\n이번 검토 DB에 일치하는 주의 자료가 없습니다. 안전하다는 뜻은 아니며, 근거 없이 초록·주황·빨강 등급을 매기지 않습니다.")
    else:
        missing = [name for name, values in result.cautions.items() if not values]
        if missing:
            st.caption("이번 DB에 개별 주의 자료가 없는 성분: " + ", ".join(missing) + ". 자료 없음은 안전 판정이 아닙니다.")
    st.caption("원료 유래로 안전성·환경성을 판정하지 않습니다. 성분별 안내는 완제품 영향 판정과 구분해 읽어주세요.")
