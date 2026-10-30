from io import BytesIO
import json
import shutil

import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from core.database import ROOT, load_ingredients
from shared.contracts import PIPELINE_VERSION
from ui import site


def test_kcia_exact_aliases_review_and_unreviewed_names_keep_separate_meanings():
    db = load_ingredients()
    assert len(db.records) == 32797 and len(db.index) == 57706
    for name in ['쌀겨수', '호호바에스터']:
        assert db.find(name).origin == '식물성'
    assert db.find('쌀겨수') is db.find('Oryza Sativa (Rice) Bran Water')
    assert db.find('글리세린').uncertainty_reason == 'origin_uncertain'
    assert db.find('알진').origin == '확인 필요'
    assert db.find('1,2-헥산다이올') != db.find('1,3-헥산다이올')
    assert db.curated_count == 394 and db.registry_count == 32403
    assert PIPELINE_VERSION != 'starter-1'


def test_new_review_is_used_by_result_graph_and_pdf_after_one_confirmation():
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=30).run()
    app.text_area(key='input_text').set_value('쌀겨수,호호바에스터,글리세린,포타슘하이드록사이드').run()
    assert app.session_state['result'] is None
    app.button(key='confirm').click().run()
    assert not app.exception
    result = app.session_state['result']
    assert result.count_ratio.denominator == 4
    assert result.count_ratio.values['식물성'] == 50
    assert result.count_ratio.values['확인 필요'] == 25
    assert any('제조 원료 공급원 확인 필요 1개' in c.value for c in app.caption)
    text = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(app.session_state['pdf_export']['data'])).pages)
    assert 'kcia.or.kr' in text and '50.0%' in text
    assert '완제품의 pH' in text


def test_unreviewed_kcia_file_edit_rejects_data_and_clears_previous_pdf(tmp_path, monkeypatch):
    shutil.copytree(ROOT/'data', tmp_path/'data')
    monkeypatch.setattr(site, 'load_ingredients', lambda: load_ingredients(tmp_path))
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=30).run()
    app.text_area(key='input_text').set_value('쌀겨수').run()
    app.button(key='confirm').click().run()
    assert 'pdf_export' in app.session_state
    path = tmp_path/'data/kcia_ingredients.csv'
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError, match='체크섬'):
        load_ingredients(tmp_path)
    app.run()
    assert app.session_state['result'] is None and 'pdf_export' not in app.session_state
    assert any('체크섬' in error.value for error in app.error)


def test_legacy_data_without_kcia_extension_still_loads(tmp_path):
    shutil.copytree(ROOT/'data', tmp_path/'data')
    for path in (tmp_path/'data').glob('kcia_*'):
        path.unlink()
    db = load_ingredients(tmp_path)
    assert len(db.records) == 28347 and db.curated_count == 270


def test_changed_base_cannot_be_silently_overwritten_by_old_overlay(tmp_path):
    shutil.copytree(ROOT/'data', tmp_path/'data')
    path = tmp_path/'data/ingredients.csv'
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError, match='기본 DB'):
        load_ingredients(tmp_path)
