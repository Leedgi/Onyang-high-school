import hashlib
import json
import shutil

from core.database import ROOT
from scripts.build_origin_data import build, evidence_rule


def test_definition_rules_do_not_force_ambiguous_chemicals_or_algae_into_plants():
    assert evidence_rule('GLYCERIN', 'Glycerol, propane-1,2,3-triol') is None
    assert evidence_rule('CETEARYL ALCOHOL', 'A mixture of fatty alcohols') is None
    assert evidence_rule('SODIUM LACTATE', 'Lactic acid sodium salt') is None
    assert evidence_rule('TEST EXTRACT', 'Extract of Test, Unknownaceae') is None
    assert evidence_rule('TEST LEAF EXTRACT', 'Synthetic fragrance solution of Test leaf', {'TEST'}) is None
    assert evidence_rule('ROSA CANINA FRUIT EXTRACT', 'Rosa Canina Fruit Extract is a product of fermentation of fruit, Rosaceae') is None
    assert evidence_rule('PEG-40 PLANT OIL', 'Oil from seeds, Rosaceae') is None
    assert evidence_rule('LAMINARIA EXTRACT', 'Extract of Laminaria algae, Laminariaceae')[0] == '기타'
    assert evidence_rule('AGARICUS EXTRACT', 'Extract of Agaricus fungus, Agaricaceae')[0] == '기타'
    assert evidence_rule('C10-12 ALKANE/CYCLOALKANE', 'Hydrocarbons obtained by treating a petroleum fraction')[0] == '석유계'
    assert evidence_rule('ROSA CANINA SEED OIL', 'Oil expressed from seeds, Rosaceae')[0] == '식물성'


def test_origin_review_hashes_facts_and_routes_are_separate():
    data=ROOT/'data'
    manifest=json.loads((data/'origin_sources.json').read_text(encoding='utf-8'))
    for key in ['files','base_files']:
        for name,expected in manifest[key].items():
            assert hashlib.sha256((data/name).read_bytes()).hexdigest()==expected
    review=json.loads((data/'reviewed/origin_review.json').read_text(encoding='utf-8'))
    assert len({r['name'] for r in review['entries']})==manifest['classified_records']
    assert manifest['added_origin_counts']['식물성']>5000
    assert manifest['added_origin_counts']['석유계']==11
    assert all(r['definition_sha256'] and r['source_ref'] for r in review['entries'])
    assert all(r['taxonomy_ref'] for r in review['entries'] if r['rule']=='referenced_plant_genus_material')
    routes=json.loads((data/'reviewed/origin_route_review.json').read_text(encoding='utf-8'))
    assert len(routes['entries'])==5
    assert any(r['name']=='스테아릭애씨드' and '동물성' in r['summary'] for r in routes['entries'])


def test_offline_origin_generation_is_deterministic(tmp_path):
    shutil.copytree(ROOT/'data',tmp_path/'data')
    assert build(tmp_path)==build(tmp_path)==json.loads((ROOT/'data/origin_sources.json').read_text(encoding='utf-8'))
