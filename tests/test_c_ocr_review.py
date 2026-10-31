from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from streamlit.testing.v1 import AppTest

from core.models import Candidate, IngredientDraft, IngredientScan, OCRResult
from core.scan import ScanOutput
from shared.contracts import PIPELINE_VERSION
from ui import site

ROOT=Path(__file__).resolve().parents[1]


def test_ocr_proposal_auto_analyzes_and_preserves_source_without_questions(monkeypatch):
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
    assert not [x for x in app.selectbox if x.key and x.key.startswith("candidate_")]
    result=app.session_state['result']
    assert result.rows[0].canonical_name=='소듐하이드록사이드'
    assert result.automatic_decisions[0].draft.raw_text=='소듬하이드록사이드'
    app.run()
    assert len(calls)==1
    app.text_area(key='input_text').set_value('정제수').run()
    assert app.session_state['result'].rows[0].canonical_name=='정제수'
    assert len(calls)==1


def test_scan_version_changes_cache_key_and_edited_text_uses_manual_review():
    assert PIPELINE_VERSION=='ppocr-v5-korean-1'
    d=IngredientDraft('원문','제안','needs_review')
    output=ScanOutput(IngredientScan('ok',OCRResult('ok'),(d,)),Image.new('RGB',(5,5)))
    assert site.visible_review('제안',output)==(d,)
    assert site.visible_review('정 제 수',output)[0].name=='정제수'
