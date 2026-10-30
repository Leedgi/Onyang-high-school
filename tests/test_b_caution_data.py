import csv
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from core.database import ROOT, load_cautions, load_ingredients
from core.normalize import normalize_key
from features.analysis import analyze_confirmed
from scripts.build_caution_data import build
from shared.contracts import AnalysisRequest, ConfirmedIngredient


def analyze(*names):
    return analyze_confirmed(AnalysisRequest(tuple(ConfirmedIngredient(n) for n in names)))


def test_reviewed_targets_have_source_conditions_and_runtime_records():
    review = json.loads((ROOT/'data/reviewed/caution_review.json').read_text())
    records = load_cautions()
    assert len(review['ingredients']) == 30 and len(records) == 63
    for item in review['ingredients']:
        for name in item['target_names']:
            result = analyze(name)
            assert result.cautions[result.rows[0].canonical_name], name
    for record in records:
        assert all(getattr(record, name).strip() for name in record.__dataclass_fields__)
        assert record.checked_on == '2026-10-30'
        assert record.source_url.startswith(('https://www.fda.gov/', 'https://pubchem.ncbi.nlm.nih.gov/'))


def test_health_warnings_preserve_individual_and_product_uncertainty():
    result = analyze('리날룰','시트릭애씨드','살리실릭애씨드','메칠이소치아졸리논')
    records = [r for group in result.cautions.values() for r in group]
    assert len(records) == 4
    assert any('개인 감작' in r.concentration_condition for r in records)
    assert any('1주' in r.use_condition for r in records)
    assert any('영유아' in r.use_condition for r in records)
    assert all('한국' in r.country for r in records)
    limonene = next(iter(analyze('리모넨').cautions.values()))[0]
    assert 'd형을 확정하지 않습니다' in limonene.reason


def test_exact_substance_environmental_tests_not_all_silicones_or_unknowns():
    result = analyze('사이클로펜타실록세인','사이클로헥사실록세인','다이메티콘','미등록성분')
    assert result.count_ratio.denominator == 4
    assert '0.14%' in result.cautions['사이클로펜타실록세인'][0].reason
    assert '4.47%' in result.cautions['사이클로헥사실록세인'][0].reason
    assert not result.cautions['다이메티콘'] and not result.cautions['미등록성분']
    d4 = next(iter(analyze('사이클로테트라실록세인').cautions.values()))[0]
    assert '556-67-2' in d4.restriction and '복수 CAS' in d4.restriction
    for name in ['리날룰123','사이클로메티콘','정제수']:
        assert not any(analyze(name).cautions.values())


def test_environmental_csv_preserves_test_endpoint_dose_and_historical_scope():
    with (ROOT/'data/environmental_evidence.csv').open() as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 3
    assert [(r['test_duration_days'],r['test_result_percent']) for r in rows] == [('29','3.7'),('28','0.14'),('28','4.47')]
    assert rows[1]['test_concentration'] == '20 mg/L'
    assert 'CO2' in rows[1]['test_endpoint']
    assert '미기재' in rows[2]['test_concentration']
    assert '2008' in rows[2]['source_date_note']
    assert '완제품' in rows[1]['limitations']


def test_sources_counts_hashes_unique_targets_and_reproducible_build(tmp_path):
    manifest = json.loads((ROOT/'data/caution_sources.json').read_text())
    assert (manifest['reviewed_substances'],manifest['human_substances'],manifest['environmental_substances']) == (30,27,3)
    assert manifest['sources']['fda-allergens']['source_updated_on'] == '2026-10-09'
    assert manifest['sources']['fda-aha']['source_updated_on'] == '2022-11-22'
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest() == digest
    keys = [normalize_key(r.name) for r in load_cautions()]
    assert len(keys) == len(set(keys))
    shutil.copytree(ROOT/'data', tmp_path/'data')
    assert build(tmp_path) == manifest
    assert build(tmp_path) == manifest
    for name in manifest['files']:
        assert (tmp_path/'data'/name).read_bytes() == (ROOT/'data'/name).read_bytes()
