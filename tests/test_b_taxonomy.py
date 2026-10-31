import hashlib
import json
import shutil

import pytest

from core.database import ROOT, load_ingredients, load_cautions
from core.models import ConfirmedIngredient, DETAIL_ORIGINS
from core.analysis import analyze
from scripts.build_taxonomy_data import build, FILES


def test_imported_taxonomy_has_expected_categories_but_does_not_certify_estimates():
    db=load_ingredients()
    assert len(db.records)==32797 and len(db.index)==57706
    assert db.curated_count==6143 and db.registry_count==26654
    assert db.detail_origin_counts=={'식물 유래':11551,'동물 유래':634,'광물·무기물':510,'발효·미생물 유래':1706,'석유계':17,'합성':9846,'확인 필요':8533}
    inferred=db.find('VACCINIUM MACROCARPON (CRANBERRY) SEED OIL')
    assert inferred.origin=='확인 필요'
    assert inferred.detail_origin=='식물 유래' and inferred.detail_is_estimate
    assert inferred.uncertainty_reason=='evidence_insufficient'
    assert db.find('글리세린').origin=='확인 필요'
    assert db.find('글리세린').detail_origin=='확인 필요'
    assert db.find('글리세린').uncertainty_reason=='origin_uncertain'
    assert db.find('SYNTHETIC BEESWAX').detail_origin=='합성'
    assert '명시' in db.find('SYNTHETIC BEESWAX').detail_reason


def test_detailed_ratio_uses_same_confirmed_names_and_keeps_unknown_in_denominator():
    db=load_ingredients()
    result=analyze([ConfirmedIngredient('VACCINIUM MACROCARPON (CRANBERRY) SEED OIL'),ConfirmedIngredient('전혀새원료')],db,[])
    assert result.detail_count_ratio.denominator==result.count_ratio.denominator==2
    assert tuple(result.detail_count_ratio.values)==DETAIL_ORIGINS
    assert result.detail_count_ratio.values['식물 유래']==50
    assert result.detail_count_ratio.values['확인 필요']==50
    assert sum(result.detail_count_ratio.values.values())==100
    assert result.count_ratio.values['확인 필요']==100
    assert result.rows[0].confirmed.amount is None
    assert result.rows[0].detail_is_estimate and result.rows[1].uncertainty_reason=='db_missing'


def test_additional_aha_conditions_remain_limited_and_sourced():
    records=load_cautions()
    assert len(records)==66
    added=[r for r in records if r.name in {'MANDELIC ACID','MALIC ACID','TARTARIC ACID'}]
    assert len(added)==3
    assert all('FDA' in r.country and 'pH' in r.concentration_condition for r in added)


def test_source_manifest_checks_audit_and_generator_is_repeatable(tmp_path):
    shutil.copytree(ROOT/'data',tmp_path/'data')
    before={p.name:p.read_bytes() for p in (tmp_path/'data').iterdir() if p.is_file()}
    build(tmp_path)
    assert {p.name:p.read_bytes() for p in (tmp_path/'data').iterdir() if p.is_file()}==before
    manifest=json.loads((tmp_path/'data/origin_taxonomy_sources.json').read_text())
    assert set(manifest['files'])==set(FILES)
    assert all(hashlib.sha256((tmp_path/'data'/name).read_bytes()).hexdigest()==sha for name,sha in manifest['files'].items())
    p=tmp_path/'data/origin_detail_audit.csv';p.write_bytes(p.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='체크섬'):load_ingredients(tmp_path)
