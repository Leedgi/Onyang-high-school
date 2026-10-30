import csv
from io import BytesIO
from pathlib import Path
import shutil

from pypdf import PdfReader
import pytest
from streamlit.testing.v1 import AppTest

from core.database import ROOT, load_ingredients, load_cautions
from features.analysis import analyze_confirmed
from shared.contracts import AnalysisRequest, ConfirmedIngredient
from ui import site


def test_verified_korean_alias_and_inci_deduplicate_without_changing_origin():
    r = analyze_confirmed(AnalysisRequest(tuple(ConfirmedIngredient(n) for n in ['리모넨','LIMONENE'])))
    assert len(r.rows) == 1 and r.rows[0].canonical_name == 'LIMONENE'
    assert r.rows[0].origin == '확인 필요'
    assert r.count_ratio.denominator == 1
    assert [x.name for x in r.input_records] == ['리모넨','LIMONENE']
    assert len(r.cautions['LIMONENE']) == 1
    assert load_ingredients().curated_count == 270
    assert load_ingredients().registry_count == 28077


def test_alias_collision_is_rejected_and_old_data_without_alias_file_still_loads(tmp_path):
    shutil.copytree(ROOT/'data', tmp_path/'data')
    file=tmp_path/'data/caution_aliases.csv'
    with file.open(encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    rows[0]['alias']='정제수';rows[0]['inci']='LIMONENE'
    with file.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    with pytest.raises(ValueError,match='충돌'):
        load_ingredients(tmp_path)
    file.unlink()
    assert load_ingredients(tmp_path).find('정제수').origin == '기타'


def test_changed_caution_data_clears_old_result_pdf_and_rejects_unreviewed_bytes(tmp_path,monkeypatch):
    shutil.copytree(ROOT/'data',tmp_path/'data')
    monkeypatch.setattr(site,'load_ingredients',lambda:load_ingredients(tmp_path))
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run()
    app.text_area(key='input_text').set_value('리날룰').run()
    app.button(key='confirm').click().run()
    assert app.session_state['result'] is not None and 'pdf_export' in app.session_state
    before=load_ingredients(tmp_path).fingerprint
    file=tmp_path/'data/cautions.csv';file.write_bytes(file.read_bytes()+b'\n')
    assert load_ingredients(tmp_path).fingerprint != before
    app.run()
    assert app.session_state['result'] is None and 'pdf_export' not in app.session_state
    with pytest.raises(ValueError,match='체크섬'):
        load_cautions(tmp_path)


def test_health_and_environment_cards_and_pdf_preserve_sources_and_conditions():
    app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run()
    app.text_area(key='input_text').set_value('리날룰,사이클로펜타실록세인,정제수').run()
    app.button(key='confirm').click().run()
    assert not app.exception
    warnings='\n'.join(w.value for w in app.warning)
    assert '인체 영향 · 성분별 주의 있음' in warnings
    assert '환경 영향 · 성분별 시험자료 있음' in warnings
    assert not app.info
    captions='\n'.join(c.value for c in app.caption)
    assert '자료 확인일: 2026-10-30' in captions
    assert '개별 주의 자료가 없는 성분: 정제수' in captions
    pdf=PdfReader(BytesIO(app.session_state['pdf_export']['data']))
    text='\n'.join(p.extract_text() for p in pdf.pages)
    assert '0.14%' in text and '20 mg/L' in text and '2015' in text
    assert '2026-10-09' in text and 'www.fda.gov' in text
    assert 'pubchem.ncbi.nlm.nih.gov' in text
    assert '제품 함량' in text
