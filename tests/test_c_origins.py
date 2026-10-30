from io import BytesIO
import shutil

from pypdf import PdfReader
import pytest
from streamlit.testing.v1 import AppTest

from core.database import ROOT, load_ingredients
from shared.contracts import AnalysisRequest, ConfirmedIngredient
from features.analysis import analyze_confirmed
from ui import site


def test_supported_origins_reach_same_confirmed_result_without_forcing_mixed_supply():
    names=['로즈힙씨추출물','C10-12 ALKANE/CYCLOALKANE','LAMINARIA SACCHARINA EXTRACT','글리세린']
    result=analyze_confirmed(AnalysisRequest(tuple(ConfirmedIngredient(n) for n in names)))
    assert [r.origin for r in result.rows]==['식물성','석유계','기타','확인 필요']
    assert all(value==25 for value in result.count_ratio.values.values())
    assert result.rows[-1].uncertainty_reason=='origin_uncertain'
    assert '[제조 경로 참고]' in result.rows[-1].reason


def test_mixed_supply_routes_are_visible_and_exported_but_not_counted_as_known():
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    app.text_area(key='input_text').set_value('로즈힙씨추출물,스테아릭애씨드,세틸알코올').run()
    app.button(key='confirm').click().run()
    assert not app.exception
    assert app.session_state['result'].count_ratio.values['확인 필요']==pytest.approx(200/3)
    assert any('제조 경로 참고' in item.label for item in app.expander)
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(app.session_state['pdf_export']['data'])).pages)
    assert '식물성·동물성' in text and 'pubchem.ncbi.nlm.nih.gov' in text
    assert '2019' in text and '규칙 대조' in text


def test_changed_origin_review_rejects_database_and_clears_old_pdf(tmp_path,monkeypatch):
    shutil.copytree(ROOT/'data',tmp_path/'data')
    monkeypatch.setattr(site,'load_ingredients',lambda:load_ingredients(tmp_path))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    app.text_area(key='input_text').set_value('로즈힙씨추출물').run()
    app.button(key='confirm').click().run()
    assert 'pdf_export' in app.session_state
    path=tmp_path/'data/reviewed/origin_review.json';path.write_bytes(path.read_bytes()+b'\n')
    app.run()
    assert app.session_state['result'] is None and 'pdf_export' not in app.session_state
    assert any('체크섬' in x.value for x in app.error)
