from dataclasses import replace
from io import BytesIO

from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from features.analysis import analyze_confirmed
from shared.contracts import AnalysisRequest, ConfirmedIngredient
from ui.reporting import build_pdf, ingredient_groups
from ui.review_notes import review_notes
from ui import site
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def result(*names):
    return analyze_confirmed(AnalysisRequest(tuple(ConfirmedIngredient(n) for n in names)))


def test_groups_preserve_rows_and_pdf_contains_same_percentages_and_korean():
    report = result("정제수", "미네랄오일", "시어버터", "미등록기호<&>", "정제수")
    groups = ingredient_groups(report)
    assert sum(len(rows) for _, rows in groups) == 4
    assert [row.canonical_name for origin, rows in groups for row in rows if origin == "광물·무기물"] == ["정제수"]
    data = build_pdf(report)
    pdf = PdfReader(BytesIO(data))
    text = "\n".join(page.extract_text() for page in pdf.pages)
    for row in report.rows:
        assert row.canonical_name in text
    assert "25.0%" in text and "4개 성분" in text
    assert "배합 함량이 아닙니다" in text
    assert "pH" in text and "생분해성" in text and "출처:" in text
    assert "산성도(pH) · 확인 불가" in text
    assert b"/FontFile2" in data  # Korean font is embedded, not left to the viewer.


def test_long_pdf_paginates_instead_of_losing_rows():
    base = result("정제수")
    rows = tuple(replace(base.rows[0], canonical_name=f"긴성분이름-{n}",
                         functions=("긴 기능 설명 " * 30,)) for n in range(90))
    report = replace(base, rows=rows, count_ratio=replace(base.count_ratio, denominator=90),
                     detail_count_ratio=replace(base.detail_count_ratio, denominator=90))
    pdf = PdfReader(BytesIO(build_pdf(report)))
    assert len(pdf.pages) > 3
    text = "\n".join(page.extract_text() for page in pdf.pages)
    for i in range(90):
        assert f"긴성분이름-{i}" in text
    assert "90개 성분" in text
    assert "등록된 주의 자료가 없습니다" in text


def test_acid_and_base_do_not_become_product_ph_or_environmental_rating():
    report = result("시트릭애씨드", "소듐하이드록사이드", "다이메티콘", "미등록성분")
    notes = review_notes(report)
    assert notes[0][0] == "산성도(pH) · 확인 불가"
    assert "시트릭애씨드" in notes[0][1] and "소듐하이드록사이드" in notes[0][1]
    assert "산성·염기성을 판정할 수 없습니다" in notes[0][1]
    assert notes[2][0] == "환경 영향 · 자료 부족"
    assert report.cautions["시트릭애씨드"][0].reason.startswith("[인체·AHA]")
    assert not report.cautions["다이메티콘"]


def test_pdf_is_session_local_and_invalidated_with_input(monkeypatch):
    calls = []
    original = site.build_pdf

    def export(report):
        calls.append(report)
        return original(report)

    monkeypatch.setattr(site, "build_pdf", export)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    app.text_area(key="input_text").set_value("정제수,미네랄오일").run()
    app.button(key="confirm").click().run()
    assert not app.exception
    assert len(calls) == 1
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(app.session_state["pdf_export"]["data"])).pages)
    assert "미네랄오일" in text
    assert list(app.dataframe[0].value["성분"]) == ["정제수"]
    assert list(app.dataframe[1].value["성분"]) == ["미네랄오일"]
    app.run()
    assert len(calls) == 1
    other = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert "pdf_export" not in other.session_state
    app.text_area(key="input_text").set_value("정제수").run()
    assert "pdf_export" not in app.session_state
    app.button(key="confirm").click().run()
    assert len(calls) == 2
    updated = "\n".join(p.extract_text() for p in PdfReader(BytesIO(app.session_state["pdf_export"]["data"])).pages)
    assert "미네랄오일" not in updated
