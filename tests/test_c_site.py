from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from core.models import IngredientScan, OCRResult
from core.scan import ScanOutput
from features.recognition import prepare_review
from ui import site

ROOT = Path(__file__).resolve().parents[1]


def app():
    result = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    assert not result.exception
    return result


def test_no_demo_and_single_confirmation():
    page = app()
    assert len(page.radio) == 0
    assert page.session_state["result"] is None
    page.text_area(key="input_text").set_value("] 정 제 수, 글 리 세 린").run()
    assert page.session_state["result"] is None
    page.button(key="confirm").click().run()
    assert not page.exception
    assert [r.canonical_name for r in page.session_state["result"].rows] == ["정제수", "글리세린"]
    page.text_area(key="input_text").set_value("미등록성분").run()
    assert page.session_state["result"] is None


def test_candidate_selection_clears_previous_result_without_apply_button():
    page = app()
    page.text_area(key="input_text").set_value("미네활오잃").run()
    page.button(key="confirm").click().run()
    assert page.session_state["result"].rows[0].uncertainty_reason == "db_missing"
    page.selectbox[0].set_value("미네랄오일").run()
    assert page.session_state["result"] is None
    page.button(key="confirm").click().run()
    assert not page.exception
    assert page.session_state["result"].rows[0].canonical_name == "미네랄오일"
    assert len(page.button) == 1


def test_upload_automatically_runs_once_then_new_photo_invalidates(monkeypatch):
    upload = [SimpleNamespace(name="first.png", getvalue=lambda: b"test-first")]
    monkeypatch.setattr(site.st, "file_uploader", lambda *args, **kwargs: upload[0])
    monkeypatch.setattr(site, "get_engine", object)
    calls = []

    def recognize(data, filename, **kwargs):
        from PIL import Image
        calls.append(filename)
        # 명시적인 모의 인식. 실제 사진 OCR 성능 검사와 구분한다.
        result = IngredientScan("ok", OCRResult("ok", raw_text="정제수"), prepare_review("정제수"))
        return ScanOutput(result, Image.new("RGB", (40, 40), "white"))

    monkeypatch.setattr(site, "recognize_photo", recognize)
    page = app()
    assert calls == ["first.png"]
    assert page.session_state["result"] is None
    page.button(key="confirm").click().run()
    assert calls == ["first.png"]
    assert page.session_state["result"] is not None
    upload[0] = SimpleNamespace(name="second.png", getvalue=lambda: b"test-second")
    page.run()
    assert not page.exception
    assert calls == ["first.png", "second.png"]
    assert page.session_state["result"] is None
    upload[0] = None
    page.run()
    assert not page.exception
    assert page.text_area(key="input_text").value == ""
    assert page.session_state["scan_output"] is None


def test_photo_failure_retains_retry_and_manual_recovery(monkeypatch):
    monkeypatch.setattr(site.st, "file_uploader", lambda *a, **k: SimpleNamespace(name="bad.jpg", getvalue=lambda: b"bad"))
    monkeypatch.setattr(site, "get_engine", object)

    def fail(*args, **kwargs):
        raise ValueError("손상된 사진")

    monkeypatch.setattr(site, "recognize_photo", fail)
    page = app()
    page.run()
    assert page.button(key="retry")
    assert page.error
    page.text_area(key="input_text").set_value("정제수").run()
    page.button(key="confirm").click().run()
    assert not page.exception
    assert page.session_state["result"].rows[0].canonical_name == "정제수"


def test_sessions_keep_results_separate():
    first = app()
    first.text_area(key="input_text").set_value("정제수").run()
    first.button(key="confirm").click().run()
    second = app()
    assert first.session_state["result"] is not None
    assert second.session_state["result"] is None


def test_donut_keeps_unknowns_and_does_not_invent_safety_grades():
    import json

    page = app()
    assert page.title[0].value == "친환경 제품 성분 정보 분석"
    page.text_area(key="input_text").set_value("정제수, 미등록성분").run()
    assert not page.get("vega_lite_chart")
    page.button(key="confirm").click().run()
    assert not page.exception
    spec = json.loads(page.get("vega_lite_chart")[0].proto.spec)
    assert spec["layer"][0]["mark"]["type"] == "arc"
    assert spec["layer"][0]["mark"]["innerRadius"] > 0
    assert "확인 필요" in spec["layer"][0]["encoding"]["color"]["scale"]["domain"]
    assert page.session_state["result"].count_ratio.denominator == 2
    assert page.session_state["result"].count_ratio.values["확인 필요"] == 50
    assert any("자료 부족" in info.value for info in page.info)
    page.text_area(key="input_text").set_value("정제수").run()
    assert not page.get("vega_lite_chart")
