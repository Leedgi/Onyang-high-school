"""학생 C: 업로드 → 자동 이름 선택·분석 → 결과. 원문·제외는 세션에 보존."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import altair as alt

import pandas as pd
import streamlit as st

from ui.presentation import intro, upload_help, ratio_summary, footer
from ui.reporting import ingredient_groups, build_pdf, visible_ratio, origin_label, COLORS
from ui.automatic import resolve_automatically
from ui.review_notes import review_notes
from ui.cautions import render_cautions
from ui.chemistry_panel import render_chemistry_panel

from core.database import load_ingredients
from core.ocr import OCREngine
from features.analysis import analyze_confirmed
from features.recognition import prepare_review, recognize_photo
from shared.contracts import CONTRACT_VERSION, AnalysisRequest, ConfirmedIngredient, PIPELINE_VERSION, SESSION_DEFAULTS


@st.cache_resource(max_entries=1)
def _cached_engine(pipeline_version: str) -> OCREngine:
    return OCREngine()


def get_engine() -> OCREngine:
    return _cached_engine(PIPELINE_VERSION)


def visible_review(text, output):
    # 자동 제안명을 다시 exact로 대조해 미확정 상태를 잃지 않는다.
    if output is not None and output.result.status == "ok":
        initial = "\n".join(d.name for d in output.result.ingredients)
        if text == initial:
            return output.result.ingredients
    return prepare_review(text)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def clear_result() -> None:
    st.session_state.result = None
    st.session_state.pop("pdf_export", None)


def reset_source(key) -> None:
    for name in ("scan_output", "result", "review_signature"):
        st.session_state[name] = None
    st.session_state.input_text = ""
    st.session_state.source_error = None
    st.session_state.stage = "idle"
    st.session_state.source_key = key
    st.session_state.pop("pdf_export", None)


def render_chart(ratio) -> None:
    frame = pd.DataFrame({"유래": ratio.values.keys(), "비율 (%)": ratio.values.values()})
    # Radius follows the available view size, including narrow phone screens.
    base = alt.Chart(frame).encode(
        theta=alt.Theta("비율 (%):Q", stack=True),
        order=alt.Order("유래:N", sort="ascending"),
    )
    chart = base.mark_arc(
        innerRadius=alt.ExprRef(expr="min(width, height) * 0.22"),
        outerRadius=alt.ExprRef(expr="min(width, height) * 0.43"),
    ).encode(
        color=alt.Color("유래:N", scale=alt.Scale(
            domain=list(COLORS),
            range=list(COLORS.values()),
        ), legend=None),
        tooltip=[alt.Tooltip("유래:N"), alt.Tooltip("비율 (%):Q", format=".1f")],
    )
    labels = base.transform_calculate(
        percentage="datum['비율 (%)'] > 0 ? format(datum['비율 (%)'], '.1f') + '%' : ''",
    ).mark_text(
        radius=alt.ExprRef(expr="min(width, height) * 0.33"),
        fontSize=13, fontWeight=600,
    ).encode(
        text="percentage:N",
        color=alt.condition(
            "datum['유래'] === '석유계'",
            alt.value("#ffffff"), alt.value("#1a3524"),
        ),
    )
    total = alt.Chart(pd.DataFrame({"표시": [f"{int(ratio.denominator)}개 성분"]})).mark_text(
        fontSize=18, fontWeight=600, color="#183f31",
    ).encode(text="표시:N")
    st.altair_chart(
        (chart + labels + total).properties(height=340, padding={"left": 16, "right": 16, "top": 16, "bottom": 16}, background="#ffffff")
        .configure_view(stroke=None), width="stretch",
    )


def render_result(result) -> None:
    if result.status == "no_data":
        st.warning(f"분석할 성분을 식별하지 못했습니다. {len(result.automatic_decisions)}개 항목을 제외했습니다. 사진을 다시 올리거나 목록을 수정해 주세요." if result.automatic else "분석할 성분이 없습니다.")
        return
    with st.container(key="results"):
        st.html('<div id="results" class="result-heading"><p class="eyebrow">내 성분 리포트</p></div>')
        st.subheader("성분 분석 결과")
        st.caption("분석에 포함한 성분만의 결과입니다. 사진·입력을 바꾸면 이전 결과를 지웁니다.")
        if result.automatic:
            excluded = sum(not d.selected_name for d in result.automatic_decisions)
            estimated = sum(bool(d.selected_name) and d.reason != "DB 이름 일치" for d in result.automatic_decisions)
            st.caption(f"이름 자동 추정 {estimated}개 · 미식별 제외 {excluded}개. 비율은 제외 후 중복을 뺀 성분 수 기준이며 전체 성분표의 비율이 아닐 수 있습니다.")
        with st.container(key="ratio-card"):
            visual, summary = st.columns([1, 1.1], gap="large", vertical_alignment="center")
            with visual:
                render_chart(visible_ratio(result))
            with summary:
                ratio_summary(visible_ratio(result))
        ingredients, chemistry_tab, cautions_tab, evidence = st.tabs(["성분 목록", "화학 분석", "주의 정보", "자료 안내"])
        with ingredients:
            if result.detail_count_ratio:
                st.info("7분류에는 이름 규칙 기반 추정이 포함됩니다. ‘(추정)’은 제조사의 실제 원료를 확인한 결과가 아닙니다. 합성은 석유계와 같은 뜻이 아닙니다.")
            st.caption("성분을 유래별로 묶었습니다. 각 묶음 안에서는 원래 목록 순서를 유지합니다.")
            for origin, rows in ingredient_groups(result):
                st.subheader(f"{origin} · {len(rows)}개")
                if origin == "확인 필요" and rows:
                    reasons = {"origin_uncertain": "제조 원료 공급원 확인 필요",
                               "evidence_insufficient": "이름은 등록됐지만 유래 근거 부족",
                               "db_missing": "DB 미등록", "name_unresolved": "이름 대조 미확정"}
                    st.caption(" · ".join(f"{label} {sum(r.uncertainty_reason == code for r in rows)}개"
                                          for code, label in reasons.items()
                                          if any(r.uncertainty_reason == code for r in rows)))
                if rows:
                    st.dataframe([{
                        "성분": row.canonical_name, "유래": origin_label(row), "기능": ", ".join(row.functions),
                    } for row in rows], hide_index=True, width="stretch")
                else:
                    st.caption("해당 성분 없음")
            routes = [row for row in result.rows if row.reason.startswith("[제조 경로 참고]")]
            if routes:
                with st.expander("식물성일까, 석유계일까? · 제조 경로 참고"):
                    st.caption("같은 성분도 제조 원료가 달라질 수 있습니다. 아래는 과거에 기록된 가능한 제조법이며 내 제품의 유래 판정은 아닙니다.")
                    for row in routes:
                        st.markdown(f"**{row.canonical_name}**")
                        st.write(row.reason.removeprefix("[제조 경로 참고] "))
                        st.link_button("제조 경로 원문", row.source_url)
        with chemistry_tab:
            render_chemistry_panel(result)
        with cautions_tab:
            for label, description in review_notes(result):
                st.warning(f"{label}\n\n{description}")
            render_cautions(result)
        with evidence:
            with st.expander("자동 선택·제외 내역"):
                st.dataframe([{ "원문": d.draft.raw_text, "선택": d.selected_name or "제외", "처리": d.reason } for d in result.automatic_decisions], hide_index=True)
            st.write("확인이 필요한 이유와 원문 출처")
            st.dataframe([{
                "성분": row.canonical_name, "확인 필요 원인": row.uncertainty_reason,
                "근거": row.reason, "출처": row.source_url, "확인일": row.checked_on,
                "7분류": origin_label(row), "7분류 검토 수준": row.detail_confidence,
                "7분류 근거": row.detail_reason, "7분류 자료 출처": row.detail_source_url,
            } for row in result.rows], hide_index=True, width="stretch")
            st.caption("일부 근거는 2019년 자료입니다. 최신 규제·안전성 검토를 대신하지 않으며, 이름 등재만으로 유래·사용 허용을 판단하지 않습니다.")
        signature = digest(asdict(result))
        try:
            cached = st.session_state.get("pdf_export")
            if cached is None or cached["signature"] != signature:
                cached = {"signature": signature, "data": build_pdf(result)}
                st.session_state.pdf_export = cached
            st.download_button("PDF 분석 리포트 저장", cached["data"],
                               file_name="ingredient-analysis.pdf", mime="application/pdf",
                               icon=":material/download:", key="analysis_pdf", on_click="ignore")
            st.caption("그래프·유래별 성분표·평가 한계·출처를 함께 저장합니다. 사진과 인식 원문은 PDF에 자동 첨부하지 않습니다.")
        except ImportError:
            st.error("PDF 저장 기능의 추가 설치가 필요합니다. setup_windows.bat을 한 번 실행한 뒤 앱을 다시 시작해 주세요.")
        except Exception:
            st.error("PDF를 만들지 못했습니다. 분석 결과는 화면에서 확인할 수 있습니다. 오류가 계속되면 하단에서 제보해 주세요.")


def main() -> None:
    st.set_page_config(page_title="친환경 제품 성분 정보 분석", page_icon="🌿", layout="wide")
    st.html("<style>" + Path(__file__).with_name("styles.css").read_text(encoding="utf-8") + "</style>")
    for name, value in SESSION_DEFAULTS.items():
        st.session_state.setdefault(name, value)
    intro()
    with st.container(key="upload-panel"):
        upload, tips = st.columns([1.35, 1], gap="large", vertical_alignment="center")
        with upload:
            st.html('<div class="panel-label"><span>01</span><h3>성분표 사진 올리기</h3><em class="single-badge">한 번에 1장</em></div>')
            with st.container(key="single-photo"):
                st.html('''<div class="single-photo-intro"><span class="single-photo-icon" aria-hidden="true"></span><div><strong>사진은 한 장씩.</strong><p>전성분이 모두 보이는 사진을 선택해 주세요.</p></div></div>''')
                uploaded = st.file_uploader("성분표 사진 1장 선택", type=["jpg", "jpeg", "png", "heic", "heif"],
                                           accept_multiple_files=False, key="photo",
                                           help="한 번에 사진 1장만 분석합니다. 다른 사진은 현재 파일을 삭제한 뒤 선택해 주세요.")
                st.caption("JPG · PNG · HEIC · HEIF / 최대 10MB, 2천만 화소")
            st.caption("선택하면 바로 자동 분석합니다. 다른 사진은 현재 파일을 삭제한 뒤 올려주세요.")
        with tips:
            upload_help()
    try:
        database = load_ingredients()
    except (OSError, ValueError) as exc:
        clear_result()
        st.error(f"성분 자료를 불러오지 못했습니다: {exc}")
        footer()
        return
    if uploaded is not None:
        data = uploaded.getvalue()
        source_key = digest([hashlib.sha256(data).hexdigest(), uploaded.name, database.fingerprint,
                             PIPELINE_VERSION, st.session_state.retry_nonce])
        if source_key != st.session_state.source_key:
            reset_source(source_key)
            st.session_state.stage = "recognizing"
            try:
                with st.status("성분표를 자동으로 읽고 있습니다", expanded=False) as status:
                    output = recognize_photo(data, uploaded.name, engine=get_engine(),
                                             progress=lambda message: status.update(label=message))
                    st.session_state.scan_output = output
                    success = output.result.status == "ok"
                    status.update(label="성분 분석을 준비하고 있습니다" if success else "사진을 확인해 주세요",
                                  state="complete" if success else "error")
                if success:
                    st.session_state.input_text = "\n".join(draft.name for draft in output.result.ingredients)
                    st.session_state.stage = "review"
                else:
                    st.session_state.stage = "error"
            except (ValueError, OSError, RuntimeError) as exc:
                st.session_state.stage = "error"
                st.session_state.source_error = f"사진을 처리하지 못했습니다: {exc}"
        if st.session_state.source_error:
            st.error(st.session_state.source_error)
        output = st.session_state.scan_output
        if output is not None:
            with st.expander("자동 보정한 사진 보기", expanded=False):
                st.image(output.image, caption="자동으로 보정한 성분표", width="stretch")
            if output.result.status != "ok":
                st.warning(output.result.message or "성분 목록을 읽지 못했습니다. 아래에 직접 입력할 수 있습니다.")
            for warning in output.result.warnings:
                st.warning(warning)
            with st.expander("인식 원문과 정리 과정"):
                st.code(output.result.ocr.raw_text, language=None)
                st.dataframe([{"원문": d.raw_text, "제안": d.name, "상태": d.status,
                               "정리": " / ".join(d.transformations)} for d in output.result.ingredients], hide_index=True)
        failed_photo = st.session_state.source_error or output is not None and output.result.status != "ok"
        if failed_photo and st.button("사진 다시 읽기", key="retry"):
            st.session_state.retry_nonce += 1
            st.rerun()
    elif st.session_state.source_key is not None:
        reset_source(None)
    with st.container(key="review-panel"):
        st.html('<div id="review" class="panel-label"><span>02</span><h3>자동으로 정리한 성분</h3></div>')
        with st.expander("성분 목록 확인 · 직접 입력", expanded=False):
            st.caption("사진은 자동으로 분석합니다. 필요하면 목록을 수정하거나 사진 없이 직접 입력하세요.")
            text = st.text_area("성분 목록 확인·수정", key="input_text", height=180,
                                placeholder="사진을 올리거나 성분명을 쉼표 또는 줄바꿈으로 구분해 입력하세요.")
            try:
                drafts = visible_review(text, st.session_state.scan_output)
            except (ValueError, OSError) as exc:
                clear_result()
                st.error(f"성분 이름을 대조하지 못했습니다: {exc}")
                footer(database)
                return
            review_signature = digest([text, database.fingerprint, st.session_state.source_key])
            if review_signature != st.session_state.review_signature:
                clear_result()
                st.session_state.review_signature = review_signature
                st.session_state.stage = "review" if text.strip() else "idle"
            decisions = resolve_automatically(drafts, database)
            names = [d.selected_name for d in decisions if d.selected_name]
            selection_key = digest([review_signature, names, CONTRACT_VERSION])
            changed = st.session_state.get("selection_key") != selection_key
            if changed:
                clear_result()
                st.session_state.selection_key = selection_key
            start_manual = bool(drafts) and st.button("바로 분석", type="primary", key="confirm", width="stretch")
            auto_run = uploaded is not None and bool(drafts) and changed
            if start_manual or auto_run:
                try:
                    with st.spinner("성분 정보를 정리하고 있습니다"):
                        request = AnalysisRequest(tuple(ConfirmedIngredient(name) for name in names), automatic=True, automatic_decisions=decisions)
                        st.session_state.result = analyze_confirmed(request)
                        st.session_state.stage = "complete"
                except (ValueError, OSError) as exc:
                    clear_result()
                    st.session_state.stage = "error"
                    st.error(f"분석하지 못했습니다: {exc}")
    if st.session_state.result is not None:
        render_result(st.session_state.result)
    footer(database)
