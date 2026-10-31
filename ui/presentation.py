"""C 화면 구성. 사용자 자료는 HTML에 넣을 때 이스케이프한다."""
from html import escape
from pathlib import Path

import streamlit as st

from ui.feedback import render_error_report


def intro() -> None:
    st.html('''<nav class="site-nav" aria-label="주 메뉴">
      <a class="wordmark" href="#top"><span class="brand-symbol" aria-hidden="true">🌱</span>성분 정보 분석</a>
      <div class="nav-links"><a href="#analyze">성분표 분석</a><a href="#guide">이용 안내</a><a href="#report">오류 제보</a></div>
    </nav><div id="top"></div>''')
    with st.container(key="hero"):
        copy, visual = st.columns([1.2, 1], gap="large", vertical_alignment="center")
        with copy:
            st.html('<p class="eyebrow">매일 쓰는 제품, 조금 더 알아보기</p>')
            st.title("친환경 제품 성분 정보 분석")
            st.write("작은 글씨 속 성분, 이제 쉽게 읽어보세요.")
            st.caption("성분표 사진 한 장으로 이름을 정리하고, 원료의 유래와 근거를 차근차근 살펴보세요.")
            st.html('''<div class="hero-actions"><a class="primary-link" href="#analyze">내 성분표 분석하기 <span aria-hidden="true">→</span></a></div>
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
      <ul><li>제품 뒷면의 전성분을 모두 담아주세요.</li><li>반사되는 빛을 피하고 초점을 맞춰주세요.</li><li>사진을 수평으로 찍어주세요</li></ul>
      <p>사진이 없어도 아래에서 성분명을 직접 입력할 수 있어요.</p></aside>''')


def ratio_summary(ratio) -> None:
    colors = {"석유계": "#356351", "식물성": "#7f9d68", "기타": "#b5c7a2", "확인 필요": "#e5e7df"}
    rows = ''.join(f'<li><span><i style="background:{colors[name]}" aria-hidden="true"></i>{escape(name)}</span><strong>{value:.1f}<small>%</small></strong></li>' for name, value in ratio.values.items())
    st.html(f'''<div class="ratio-summary"><p class="eyebrow">성분명 개수 기준</p><h3>무엇으로 이루어져 있을까요?</h3><p>중복을 제외한 <strong>{int(ratio.denominator)}개 성분</strong>의 원료 유래를 살펴봅니다.</p><ul>{rows}</ul>
      <div class="quiet-note">‘확인 필요’도 비율에 포함됩니다.<br>이 비율은 실제 배합 함량이나 안전성 점수가 아닙니다.</div></div>''')


def footer(database=None) -> None:
    st.html('<div id="guide" class="section-heading"><p class="eyebrow">알고 사용하기</p><h2>자주 묻는 질문</h2></div>')
    with st.expander("식물성 성분이면 더 안전한가요?"):
        st.write("아니요. 식물성이라는 유래만으로 안전성을 판단할 수 없습니다. 사용 농도, 개인의 피부 상태, 제품의 사용 방법에 따라 영향이 달라질 수 있습니다.")
    with st.expander("‘확인 필요’는 무슨 뜻인가요?"):
        st.write("성분명이나 원료의 유래를 확인할 근거가 부족하다는 뜻입니다. 위험하거나 유해하다고 판정한 것이 아닙니다. OCR 인식 결과와 성분명을 먼저 확인해 주세요.")
    with st.expander("화학식이 표시되지 않는 성분은 왜 있나요?"):
        st.write("식물 추출물·혼합물·일부 고분자는 하나의 화학식으로 표현하기 어렵습니다. 또한 검증된 화학 정보가 아직 없는 성분은 잘못된 값을 보여주지 않기 위해 제외합니다.")
    with st.expander("산성 성분이 있으면 화장품도 산성인가요?"):
        st.write("아니요. 분석 결과는 개별 성분의 성질을 설명합니다. 완제품의 pH는 성분의 농도와 배합에 따라 달라지므로 성분표만으로 알 수 없습니다. 정제수 자체는 순수한 상태에서 25°C 기준 중성이지만, 정제수가 들어간 화장품이 중성이라는 뜻은 아닙니다.")
    with st.expander("주의 정보가 없는 성분은 안전한가요?"):
        st.write("그렇지 않습니다. 주의 정보가 없다는 것은 현재 검토한 자료에 해당 기록이 없다는 뜻입니다. 제품 전체의 안전성을 판정한 결과가 아닙니다.")
    with st.expander("어떤 자료를 사용하나요?"):
        st.write("성분명과 유래 정보는 프로젝트의 기존 성분 DB를 사용합니다. 주의 정보는 별도 검토 자료에 근거하며, 화학식과 산·염기 특성은 화면에 수록된 일부 성분의 교육용 정보입니다. 모든 성분의 안전성이나 완제품 pH를 검증한 것은 아닙니다.")
    render_error_report()
    st.html('''<footer class="site-footer"><span class="footer-brand">성분 정보 분석.</span><p>좋은 선택은, 성분을 이해하는 데서 시작됩니다.</p><small>성분 정보 제공 서비스 · 제품의 안전성 및 친환경성 인증이 아닙니다.</small></footer>''')
