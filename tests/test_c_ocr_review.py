from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from streamlit.testing.v1 import AppTest

from core.models import Candidate, IngredientDraft, IngredientScan, OCRResult
from core.scan import ScanOutput
from shared.contracts import PIPELINE_VERSION
from ui import site

ROOT=Path(__file__).resolve().parents[1]


def test_ocr_proposal_keeps_source_choice_until_single_confirmation(monkeypatch):
    candidate=Candidate('소듐하이드록사이드','소듐하이드록사이드','fuzzy',88.8)
    draft=IngredientDraft('소듬하이드록사이드','소듐하이드록사이드','correction_proposed',
                          candidates=(candidate,),original_fragment='소듬하이드록사이드')
    output=ScanOutput(IngredientScan('ok',OCRResult('ok',raw_text=draft.raw_text),(draft,)),Image.new('RGB',(80,80),'white'))
    monkeypatch.setattr(site.st,'file_uploader',lambda *a,**k:SimpleNamespace(name='mock.png',getvalue=lambda:b'mock-photo'))
    calls=[]
    def recognize(*args,**kwargs):calls.append(1);return output
    monkeypatch.setattr(site,'recognize_photo',recognize);monkeypatch.setattr(site,'get_engine',object)
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    assert not app.exception and len(calls)==1
    assert app.session_state['result'] is None and len([s for s in app.selectbox if s.key and s.key.startswith('candidate_')])==1
    assert '소듬하이드록사이드' in app.selectbox[0].label
    assert set(app.selectbox[0].options)=={'소듐하이드록사이드','소듬하이드록사이드'}
    app.button(key='confirm').click().run()
    assert app.session_state['result'].rows[0].canonical_name=='소듐하이드록사이드'
    assert len(calls)==1
    app.selectbox[0].set_value('소듬하이드록사이드').run()
    assert app.session_state['result'] is None and 'pdf_export' not in app.session_state
    app.text_area(key='input_text').set_value('정제수').run()
    assert not [s for s in app.selectbox if s.key and s.key.startswith('candidate_')] and app.session_state['result'] is None


def test_scan_version_changes_cache_key_and_edited_text_uses_manual_review():
    assert PIPELINE_VERSION=='ppocr-v5-korean-1'
    d=IngredientDraft('원문','제안','needs_review')
    output=ScanOutput(IngredientScan('ok',OCRResult('ok'),(d,)),Image.new('RGB',(5,5)))
    assert site.visible_review('제안',output)==(d,)
    assert site.visible_review('정 제 수',output)[0].name=='정제수'
