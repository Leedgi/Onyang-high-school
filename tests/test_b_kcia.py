import csv
import hashlib
import json
import shutil

from core.database import ROOT
from scripts.build_kcia_data import build


def test_kcia_review_scope_and_named_examples():
    data = ROOT / 'data'
    metadata = json.loads((data / 'kcia_sources.json').read_text())
    for name, expected in metadata['files'].items():
        assert hashlib.sha256((data / name).read_bytes()).hexdigest() == expected
    with (data / 'kcia_standard_names.csv').open() as f:
        rows = {r['kcia_id']: r for r in csv.DictReader(f)}
    assert len(rows) == 22021
    assert rows['1572']['name'] == '쌀겨수'
    assert rows['4940']['inci'] == 'Jojoba Esters'
    review = json.loads((data / 'reviewed/kcia_origin_review.json').read_text())
    by_name = {r['name']: r for r in review['entries']}
    for name in ['쌀겨수', '호호바에스터']:
        assert by_name[name]['origin'] == '식물성'
    for name in ['글리세린', '스테아릭애씨드', '소듐하이알루로네이트']:
        assert by_name[name]['origin'] == '확인 필요'
    assert by_name['포타슘하이드록사이드']['origin'] == '기타'
    assert by_name['미네랄오일']['origin'] == '석유계'
    assert all(r['definition_reviewed'] and '열람하지 않음' in r['access_scope'] for r in review['entries'])
    assert metadata['review_origin_counts']['식물성'] == 112


def test_kcia_generation_is_reproducible_without_extension_input(tmp_path):
    shutil.copytree(ROOT / 'data', tmp_path / 'data')
    first = build(tmp_path)
    second = build(tmp_path)
    original = json.loads((ROOT / 'data/kcia_sources.json').read_text())
    assert first == second == original
    assert first['added_records'] == 4450
    assert first['merged_records'] == 32797
    assert first['excluded_conflicting_aliases'] == 242
    assert not any(c['before'] != '확인 필요' for c in first['origin_changes'])
