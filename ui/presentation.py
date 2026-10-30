"""C 화면 구성. 사용자 자료는 HTML에 넣을 때 이스케이프한다."""
from html import escape
from pathlib import Path

import streamlit as st

from ui.feedback import render_error_report


def intro() -> None:
    st.html('''<nav class="site-nav" aria-label="주 메뉴">
      <a class="wordmark" href="#top"><span class="brand-symbol" aria-hidden="true">잎</span>성분 정보 분석<span class="brand-dot">.</span></a>
      <div class="nav-links"><a href="#analyze">성분표 분석</a><a href="#guide">이용 안내</a><a href="#report">오류 제보</a></div>
    </nav><div id="top"></div>''')
    with st.container(key="hero"):
        copy, visual = st.columns([1.2, 1], gap="large", vertical_alignment="center")
        with copy:
            st.html('<p class="eyebrow">매일 쓰는 제품, 조금 더 알아보기</p>')
            st.title("친환경 제품 성분 정보 분석")
            st.write("작은 글씨 속 성분, 이제 쉽게 읽어보세요.")
            st.caption("성분표 사진 한 장으로 이름을 정리하고, 원료의 유래와 근거를 차근차근 살펴보세요.")
            st.html('''<div class="hero-actions"><a class="primary-link" href="#analyze">내 성분표 분석하기 <span aria-hidden="true">→</span></a><a class="text-link" href="#guide">어떻게 이용하나요? <span aria-hidden="true">→</span></a></div>
              <p class="privacy-note">사진을 외부 AI 서비스로 보내지 않습니다.</p>''')
        with visual:
            st.image(str(Path(__file__).with_name("assets").joinpath("ingredient-study.svg")), width="stretch")
    st.html('''<ol class="journey" aria-label="분석 순서">
      <li><span>01</span><div><strong>사진 올리기</strong><small>성분표를 자동으로 읽어요</small></div></li>
      <li><span>02</span><div><strong>목록 확인하기</strong><small>불확실한 이름만 고쳐주세요</small></div></li>
      <li><span>03</span><div><strong>성분 살펴보기</strong><small>같은 목록으로 표와 그래프를 만들어요</small></div></li>
    </ol><div id="analyze" class="section-heading"><p class="eyebrow">내 제품 알아보기</p><h2>성분표부터 시작해 볼까요?</h2><p>사진을 올리면 인식부터 이름 정리까지 자동으로 진행합니다.</p></div>''')


def upload_help() -> None:
    st.html('''<aside class="upload-help"><span class="small-label">더 잘 읽히는 사진</span>
      <h3>글씨가 선명하게,<br>성분표가 한눈에.</h3>
      <ul><li>제품 뒷면의 전성분을 모두 담아주세요.</li><li>반사되는 빛을 피하고 초점을 맞춰주세요.</li><li>거꾸로 된 사진과 곡면 라벨도 자동 보정을 시도합니다.</li></ul>
      <p>사진이 없어도 아래에서 성분명을 직접 입력할 수 있어요.</p></aside>''')


def ratio_summary(ratio) -> None:
    colors = {"석유계": "#356351", "식물성": "#7f9d68", "기타": "#b5c7a2", "확인 필요": "#e5e7df"}
    rows = ''.join(f'<li><span><i style="background:{colors[name]}" aria-hidden="true"></i>{escape(name)}</span><strong>{value:.1f}<small>%</small></strong></li>' for name, value in ratio.values.items())
    st.html(f'''<div class="ratio-summary"><p class="eyebrow">성분명 개수 기준</p><h3>무엇으로 이루어져 있을까요?</h3><p>중복을 제외한 <strong>{int(ratio.denominator)}개 성분</strong>의 원료 유래를 살펴봅니다.</p><ul>{rows}</ul>
      <div class="quiet-note">‘확인 필요’도 비율에 포함됩니다.<br>이 비율은 실제 배합 함량이나 안전성 점수가 아닙니다.</div></div>''')


def footer(database=None) -> None:
    st.html('<div id="guide" class="section-heading"><p class="eyebrow">알고 사용하기</p><h2>자주 묻는 질문</h2></div>')
    with st.expander("식물성 성분이면 더 안전한가요?"):
        st.write("원료의 유래만으로 안전성이나 환경성을 판단할 수 없습니다. 이 서비스는 제품의 친환경성이나 안전성을 인증하지 않습니다.")
    with st.expander("‘확인 필요’는 무슨 뜻인가요?"):
        st.write("DB에 이름이 없거나 제조 유래·근거가 충분하지 않은 경우입니다. 위험하다는 뜻이 아닙니다. 결과의 자료 안내에서 성분별 근거를 확인할 수 있습니다.")
    with st.expander("어떤 자료를 사용하나요?"):
        if database is not None:
            st.write(f"현재 {len(database.records):,}개 성분을 검색합니다. 개별 검토·정의 규칙 대조 {database.curated_count:,}개와 이름 전용 {database.registry_count:,}개를 구분합니다. 이름 전용 항목은 유래 근거가 없어 확인 필요로 남습니다.")
        st.write("대한화장품협회 공개 표준화 명칭 목록(2026-09-30)을 연결하고, 공개 정의 144개를 별도로 검토했습니다. 회원사 전용 ‘성분의 기원’은 열람하지 않았습니다. 분류는 공개 정의를 바탕으로 한 서비스 자체 검토이며 협회 인증이 아닙니다.")
        st.write("추가 5,749개는 2019년 정의의 명시적 근거를 규칙으로 대조했습니다. 개별 수동 검토 수와 구분하며 검토한 식물 과·속과 재료 형태, 석유 원료 등의 근거가 있을 때만 분류합니다.")
        st.write("일부 기존 근거는 2019년 비공식 스냅샷입니다. 명칭 등재와 정의 검토는 최신 규제·안전성 검토를 대신하지 않습니다. 지방산·글리세린 등은 제조사의 실제 공급원 확인이 필요합니다.")
        st.write("별도 주의 DB는 FDA 안내의 인체 주의 27개 물질과 PubChem/HSDB의 생분해성 시험 3개 물질을 검토했습니다. 자료의 발표 시점과 열람일을 구분하며, 전 성분의 안전성을 검토한 것은 아닙니다.")
    render_error_report()
    st.html('''<footer class="site-footer"><span class="footer-brand">성분 정보 분석.</span><p>좋은 선택은, 성분을 이해하는 데서 시작됩니다.</p><small>성분 정보 제공 서비스 · 제품의 안전성 및 친환경성 인증이 아닙니다.</small></footer>''')
