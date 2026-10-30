"""작성한 제보 → TXT 문서 → 실행 컴퓨터 저장·사용자 다운로드. 자동 첨부 없음."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import streamlit as st

CATEGORIES = ("사진 인식", "성분 정보·분석", "화면·사용 방법", "기타")
ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Report:
    report_id: str
    filename: str
    data: bytes


def make_report(category: str, title: str, details: str) -> Report:
    title, details = title.strip(), details.strip()
    if category not in CATEGORIES or not title or not details:
        raise ValueError("제목과 오류 내용을 모두 입력해 주세요.")
    if len(title) > 100 or len(details) > 5000 or "\x00" in title + details:
        raise ValueError("제목은 100자, 오류 내용은 5,000자 이내의 일반 텍스트로 입력해 주세요.")
    now = datetime.now(timezone(timedelta(hours=9)))
    report_id = uuid4().hex
    filename = f"error-report-{now:%Y%m%d-%H%M%S}-{report_id}.txt"
    text = (
        "친환경 제품 성분 정보 분석 · 오류 제보\n"
        f"접수번호: {report_id}\n작성 시각: {now:%Y-%m-%d %H:%M:%S} (한국 시간, UTC+09:00)\n"
        f"분류: {category}\n제목: {title}\n\n오류 내용\n{'-' * 40}\n{details}\n\n"
        "이 파일에는 사용자가 작성한 제보 내용만 포함됩니다. 사진·인식 원문·분석 결과는 자동 첨부되지 않습니다.\n"
    )
    # BOM을 포함해 Windows 메모장에서도 한글을 읽을 수 있게 한다.
    return Report(report_id, filename, text.encode("utf-8-sig"))


def save_report(report: Report) -> None:
    folder = Path(os.environ.get("INGREDIENT_REPORT_DIR") or ROOT / "reports/errors")
    folder.mkdir(parents=True, exist_ok=True)
    # 파일명에는 사용자 입력을 쓰지 않는다. 기존 파일을 덮어쓰지 않는다.
    path = folder / report.filename
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(report.data)
    except OSError:
        path.unlink(missing_ok=True)
        raise


def render_error_report() -> None:
    st.html('<div id="report" class="section-heading"><p class="eyebrow">함께 개선하기</p><h2>불편했던 점을 알려주세요</h2><p>사진 인식이나 성분 정보, 화면에서 발견한 오류를 기록해 주세요.</p></div>')
    with st.expander("오류 제보 작성하기"):
        st.caption("제출한 내용은 사이트가 실행 중인 컴퓨터에 TXT로 저장됩니다. 사진·성분 목록은 자동 첨부되지 않으니, 필요한 상황만 설명해 주세요. 이름·연락처 등 개인정보는 적지 않아도 됩니다.")
        with st.form("error_report_form", clear_on_submit=False):
            category = st.selectbox("오류 유형", CATEGORIES, key="feedback_category")
            title = st.text_input("제목 (필수)", max_chars=100, key="feedback_title",
                                  placeholder="어떤 문제가 있었나요?")
            details = st.text_area("오류 내용 (필수)", max_chars=5000, height=180,
                                   key="feedback_details", placeholder="어떤 작업을 했는지, 기대한 동작과 실제로 나타난 현상을 적어주세요.")
            submitted = st.form_submit_button("오류 제보 제출", key="feedback_submit")
        if submitted:
            signature = hashlib.sha256(json.dumps([category, title.strip(), details.strip()], ensure_ascii=False).encode()).hexdigest()
            receipt = st.session_state.get("feedback_receipt")
            try:
                if receipt is None or receipt["signature"] != signature:
                    receipt = {"signature": signature, "report": make_report(category, title, details), "saved": False}
                    st.session_state.feedback_receipt = receipt
                if not receipt["saved"]:
                    save_report(receipt["report"])
                    receipt["saved"] = True
            except ValueError as exc:
                st.warning(str(exc))
            except OSError:
                st.error("제보를 실행 컴퓨터에 저장하지 못했습니다. 아직 접수되지 않았습니다. 아래 TXT 파일을 내려받아 보관하거나 다시 제출해 주세요.")
        receipt = st.session_state.get("feedback_receipt")
        if receipt:
            report = receipt["report"]
            if receipt["saved"]:
                st.success(f"마지막 제보 TXT 저장 완료 · 접수번호 {report.report_id}")
            st.caption("아래 파일은 마지막으로 제출한 내용입니다. 입력을 수정했다면 다시 제출해 주세요.")
            st.download_button("마지막 제보 TXT 내려받기", data=report.data,
                               file_name=report.filename, mime="text/plain; charset=utf-8",
                               key="feedback_download", on_click="ignore")
