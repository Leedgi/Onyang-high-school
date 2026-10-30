from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ui import feedback, site

ROOT = Path(__file__).resolve().parents[1]


def page():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert not app.exception
    return app


def fill(app):
    app.text_input(key="feedback_title").set_value("후보 선택 오류")
    app.text_area(key="feedback_details").set_value("후보를 선택했을 때 목록이 바뀌지 않았습니다.")
    return app.button(key="feedback_submit").click().run()


def test_text_files_are_unique_korean_and_never_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv("INGREDIENT_REPORT_DIR", str(tmp_path))
    reports = [feedback.make_report("사진 인식", "../같은 제목", "오류 내용\n재현 단계") for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(feedback.save_report, reports))
    assert len(list(tmp_path.glob("*.txt"))) == 4
    for report in reports:
        assert (tmp_path / report.filename).read_bytes() == report.data
        assert report.data.startswith(b"\xef\xbb\xbf")
        assert "제목: ../같은 제목" in report.data.decode("utf-8-sig")
        with pytest.raises(FileExistsError):
            feedback.save_report(report)
    with pytest.raises(ValueError):
        feedback.make_report("사진 인식", " ", "내용")


def test_form_validation_saved_download_and_session_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("INGREDIENT_REPORT_DIR", str(tmp_path))
    app = page()
    app.button(key="feedback_submit").click().run()
    assert app.warning
    assert not list(tmp_path.glob("*.txt"))
    app.text_area(key="input_text").set_value("자동 첨부되면 안 되는 분석 입력").run()
    app = fill(app)
    assert not app.exception
    assert app.success
    receipt = app.session_state["feedback_receipt"]
    assert receipt["saved"]
    report = receipt["report"]
    text = (tmp_path / report.filename).read_text(encoding="utf-8-sig")
    assert "후보 선택 오류" in text and "목록이 바뀌지 않았습니다" in text
    assert "자동 첨부되면 안 되는 분석 입력" not in text
    app.run()
    app.button(key="feedback_submit").click().run()
    assert len(list(tmp_path.glob("*.txt"))) == 1
    other = page()
    assert "feedback_receipt" not in other.session_state
    assert not other.success


def test_storage_failure_keeps_txt_and_retry_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("INGREDIENT_REPORT_DIR", str(tmp_path))
    save = feedback.save_report

    def fail(_):
        raise PermissionError("test storage unavailable")

    monkeypatch.setattr(feedback, "save_report", fail)
    app = fill(page())
    assert app.error and not app.success
    receipt = app.session_state["feedback_receipt"]
    assert not receipt["saved"] and "후보 선택 오류" in receipt["report"].data.decode("utf-8-sig")
    report_id = receipt["report"].report_id
    monkeypatch.setattr(feedback, "save_report", save)
    app.button(key="feedback_submit").click().run()
    assert app.success
    assert app.session_state["feedback_receipt"]["report"].report_id == report_id
    assert len(list(tmp_path.glob("*.txt"))) == 1


def test_feedback_available_when_database_load_fails(monkeypatch):
    def fail():
        raise ValueError("test database invalid")

    monkeypatch.setattr(site, "load_ingredients", fail)
    app = page()
    assert app.error
    assert app.text_input(key="feedback_title")
    assert app.button(key="feedback_submit")
