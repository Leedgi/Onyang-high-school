from dataclasses import replace
from io import BytesIO
import shutil

import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from core.database import ROOT,load_ingredients
from features.analysis import analyze_confirmed
from shared.contracts import CONTRACT_VERSION,AnalysisRequest,ConfirmedIngredient
from ui import site
from ui.reporting import build_pdf,ingredient_groups,origin_label,visible_ratio


def test_same_result_powers_seven_groups_chart_and_pdf_with_estimate_label():
    r=analyze_confirmed(AnalysisRequest(tuple(ConfirmedIngredient(n) for n in ['VACCINIUM MACROCARPON (CRANBERRY) SEED OIL','SYNTHETIC BEESWAX','미등록신원료'])))
    assert CONTRACT_VERSION==2
    assert len(ingredient_groups(r))==7
    assert visible_ratio(r) is r.detail_count_ratio
    assert '추정' in origin_label(r.rows[0])
    assert origin_label(r.rows[1])=='합성'
    assert r.rows[-1].origin=='확인 필요'
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(build_pdf(r))).pages)
    assert '(추정)' in text and '합성은 석유계와 같은 뜻이 아닙니다' in text
    assert '33.3%' in text and '7분류 자료 출처:' in text
    old=replace(r,detail_count_ratio=None,rows=tuple(replace(x,detail_origin='',detail_confidence='',detail_reason='',detail_source_url='',detail_is_estimate=False) for x in r.rows))
    assert len(ingredient_groups(old))==4 and visible_ratio(old) is old.count_ratio
    assert build_pdf(old).startswith(b'%PDF')


def test_taxonomy_change_rejects_stale_data_and_clears_the_pdf(tmp_path,monkeypatch):
    shutil.copytree(ROOT/'data',tmp_path/'data')
    monkeypatch.setattr(site,'load_ingredients',lambda:load_ingredients(tmp_path))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    app.text_area(key='input_text').set_value('정제수').run();app.button(key='confirm').click().run()
    assert not app.exception and 'pdf_export' in app.session_state
    p=tmp_path/'data/origin_detail_audit.csv';p.write_bytes(p.read_bytes()+b'\n')
    app.run()
    assert app.session_state['result'] is None and 'pdf_export' not in app.session_state
    assert any('체크섬' in x.value for x in app.error)
