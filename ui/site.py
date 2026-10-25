"""학생 C: 업로드 자동 인식 → 목록 확인 한 번 → 결과 자동 계산."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import altair as alt

import pandas as pd
import streamlit as st

from core.database import load_ingredients
from core.ocr import OCREngine
from features.analysis import analyze_confirmed
from features.recognition import prepare_review, recognize_photo
from shared.contracts import AnalysisRequest, ConfirmedIngredient, PIPELINE_VERSION, SESSION_DEFAULTS


@st.cache_resource
def get_engine() -> OCREngine:
    return OCREngine()


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def reset_source(key) -> None:
    for name in ("scan_output", "result", "review_signature"):
        st.session_state[name] = None
    st.session_state.input_text = ""
    st.session_state.source_error = None
    st.session_state.stage = "idle"
    st.session_state.source_key = key


def render_result(result) -> None:
    if result.status == "no_data":
        st.info("분석할 성분이 없습니다.")
        return
    st.subheader("성분 분석 결과")
    ratio = result.count_ratio
    st.caption(f"{ratio.label} · 중복을 제외한 {int(ratio.denominator)}개 기준. 배합 함량이나 안전성 점수가 아닙니다.")
    frame = pd.DataFrame({"유래": ratio.values.keys(), "비율 (%)": ratio.values.values()})
    chart = alt.Chart(frame).mark_arc(innerRadius=82, outerRadius=120).encode(
        theta=alt.Theta("비율 (%):Q", stack=True),
        color=alt.Color("유래:N", scale=alt.Scale(
            domain=["석유계", "식물성", "기타", "확인 필요"],
            range=["#7c8481", "#2a7e3b", "#94ce9a", "#d7dad9"],
        ), legend=alt.Legend(title="원료 유래", orient="bottom")),
        tooltip=[alt.Tooltip("유래:N"), alt.Tooltip("비율 (%):Q", format=".1f")],
    )
    total = alt.Chart(pd.DataFrame({"표시": [f"{int(ratio.denominator)}개 성분"]})).mark_text(
        fontSize=20, fontWeight=600, color="#203c25",
    ).encode(text="표시:N")
    st.altair_chart((chart + total).properties(height=300).configure_view(stroke=None),
                     width="stretch")
    st.dataframe(frame, hide_index=True, width="stretch")
    st.dataframe([{
        "성분": row.canonical_name, "유래": row.origin, "기능": ", ".join(row.functions),
        "확인 필요 원인": row.uncertainty_reason, "근거": row.reason, "출처": row.source_url,
    } for row in result.rows], hide_index=True, width="stretch")
    cautions = [asdict(record) for records in result.cautions.values() for record in records]
    if cautions:
        st.subheader("사용상 주의 정보")
        st.dataframe(cautions, hide_index=True)
    else:
        st.info("주의 등급 · 자료 부족\n\n등록된 사용상 주의 자료와 등급 기준이 없어 초록·주황·빨강으로 판정하지 않습니다. 자료가 없다는 것이 안전하다는 뜻은 아닙니다.")
    st.caption("원료 유래는 안전성·환경성의 판정 기준이 아닙니다. 일부 근거는 2019년 자료이며 최신 규제 검토를 대신하지 않습니다.")
    scan = st.session_state.scan_output
    audit = {"result": asdict(result), "recognition": asdict(scan.result) if scan else None,
             "review_text": st.session_state.input_text}
    st.download_button("분석 기록 받기", json.dumps(audit, ensure_ascii=False, indent=2),
                       file_name="ingredient-analysis.json", mime="application/json")


def main() -> None:
    st.set_page_config(page_title="친환경 제품 성분 정보 분석", page_icon="🌿", layout="centered")
    st.html("<style>" + Path(__file__).with_name("styles.css").read_text(encoding="utf-8") + "</style>")
    for name, value in SESSION_DEFAULTS.items():
        st.session_state.setdefault(name, value)
    st.caption("성분표에서 시작하는 꼼꼼한 선택")
    st.title("친환경 제품 성분 정보 분석")
    st.write("성분표를 올리면 자동으로 읽어 정리합니다. 목록을 확인하면 유래와 근거를 보여드립니다.")
    st.caption("성분 정보 제공 서비스입니다. 제품의 친환경성이나 안전성을 인증하지 않습니다.")
    st.divider()
    uploaded = st.file_uploader("성분표 사진", type=["jpg", "jpeg", "png", "heic", "heif"], key="photo")
    try:
        database = load_ingredients()
    except (OSError, ValueError) as exc:
        st.error(f"성분 자료를 불러오지 못했습니다: {exc}")
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
                    status.update(label="성분 목록을 확인해 주세요" if success else "사진을 확인해 주세요",
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
            st.image(output.image, caption="자동으로 보정한 성분표", width=550)
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
    text = st.text_area("성분 목록 확인·수정", key="input_text", height=160,
                        placeholder="사진을 올리거나 성분명을 쉼표 또는 줄바꿈으로 구분해 입력하세요.")
    try:
        drafts = prepare_review(text)
    except (ValueError, OSError) as exc:
        st.error(f"성분 이름을 대조하지 못했습니다: {exc}")
        return
    review_signature = digest([text, database.fingerprint, st.session_state.source_key])
    if review_signature != st.session_state.review_signature:
        st.session_state.result = None
        st.session_state.review_signature = review_signature
        st.session_state.stage = "review" if text.strip() else "idle"
    names = []
    for i, draft in enumerate(drafts):
        if draft.status in {"exact", "alias"}:
            names.append(draft.name)
            continue
        choices = [draft.name, *(candidate.name for candidate in draft.candidates if candidate.name != draft.name)]
        chosen = st.selectbox(f"{i + 1}. {draft.raw_text} · 일치하는 이름을 확인해 주세요", choices,
                              key=f"candidate_{review_signature}_{i}")
        if draft.candidates:
            st.caption("이름 유사도: " + ", ".join(f"{c.name} {c.score:.1f}점" for c in draft.candidates) + " · 정답 확률이 아닙니다.")
        names.append(chosen)
    selection_key = digest([review_signature, names])
    if st.session_state.get("selection_key") != selection_key:
        st.session_state.result = None
        st.session_state.selection_key = selection_key
    if drafts and st.button("목록 확인 완료 · 분석 보기", type="primary", key="confirm"):
        try:
            with st.spinner("성분 정보를 정리하고 있습니다"):
                request = AnalysisRequest(tuple(ConfirmedIngredient(name) for name in names))
                st.session_state.result = analyze_confirmed(request)
                st.session_state.stage = "complete"
        except (ValueError, OSError) as exc:
            st.session_state.result = None
            st.session_state.stage = "error"
            st.error(f"분석하지 못했습니다: {exc}")
    if st.session_state.result is not None:
        render_result(st.session_state.result)
