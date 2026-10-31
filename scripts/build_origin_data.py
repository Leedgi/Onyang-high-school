"""고정 정의의 명시적 근거 규칙으로 유래 확장을 생성한다. 앱은 네트워크를 쓰지 않는다."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
from tempfile import TemporaryDirectory

from core.database import ROOT, load_ingredients
from core.normalize import normalize_key
from scripts.build_ingredient_data import SOURCES, get_source, write_csv

CHECKED_ON = '2026-10-30'
# 검토한 육상 식물의 과만 허용한다. '-aceae' 접미사 자체로 식물이라 추측하지 않는다.
PLANT_FAMILIES = set('''Rosaceae Asteraceae Rutaceae Fabaceae Lamiaceae Poaceae Pinaceae Myrtaceae
Apiaceae Lauraceae Zingiberaceae Brassicaceae Liliaceae Malvaceae Cucurbitaceae Solanaceae
Ericaceae Cupressaceae Araliaceae Rubiaceae Oleaceae Orchidaceae Moraceae Euphorbiaceae
Anacardiaceae Polygonaceae Theaceae Burseraceae Ranunculaceae Betulaceae Fagaceae
Nymphaeaceae Vitaceae Palmaceae Arecaceae Cactaceae Saxifragaceae Geraniaceae Verbenaceae
Sapindaceae Boraginaceae Chenopodiaceae Sapotaceae Apocynaceae Magnoliaceae Passifloraceae
Iridaceae Piperaceae Scrophulariaceae Meliaceae Caprifoliaceae Papaveraceae Amaranthaceae
Bignoniaceae Asparagaceae Combretaceae Caryophyllaceae Juglandaceae Amaryllidaceae Sterculiaceae
Convolvulaceae Crassulaceae Plantaginaceae Hypericaceae Cyperaceae Tiliaceae Araceae Agavaceae
Gentianaceae Onagraceae Salicaceae Primulaceae Zygophyllaceae Cistaceae Punicaceae Urticaceae
Annonaceae Berberidaceae Musaceae Menispermaceae Hamamelidaceae Lythraceae Paeoniaceae
Santalaceae Violaceae Valerianaceae Acanthaceae Actinidiaceae Celastraceae Myristicaceae
Myricaceae Nyctaginaceae Elaeagnaceae Saururaceae Balsaminaceae Bixaceae Bombacaceae
Bromeliaceae Buxaceae Calophyllaceae Cannabaceae Cannaceae Capparaceae Caricaceae Cornaceae
Costaceae Dioscoreaceae Ebenaceae Eucommiaceae Ginkgoaceae Hydrophyllaceae Illiciaceae
Juncaceae Lecythidaceae Limnanthaceae Linaceae Loranthaceae Malpighiaceae Moringaceae
Nelumbonaceae Orobanchaceae Oxalidaceae Pedaliaceae Phyllanthaceae Pittosporaceae
Platanaceae Polygalaceae Portulacaceae Rhamnaceae Sarraceniaceae Schisandraceae
Simaroubaceae Smilacaceae Styracaceae Tamaricaceae Taxaceae Theophrastaceae Ulmaceae
Zamiaceae Zingiberaceae'''.split())
OTHER_FAMILIES=set('''Laminariaceae Fucaceae Sargassaceae Alariaceae Bangiaceae Caulerpaceae
Chlorellaceae Codiaceae Corallinaceae Dictyotaceae Dunaliellaceae Gelidiaceae Gigartinaceae
Gracilariaceae Hypneaceae Lessoniaceae Porphyridiaceae Scenedesmaceae Ulvaceae
Agaricaceae Boletaceae Ganodermataceae Polyporaceae Pleurotaceae Schizophyllaceae
Auriculariaceae Morchellaceae Tremellaceae'''.split())
SIMPLE_MATERIAL = re.compile(r'\b(EXTRACT|OIL|WATER|JUICE|POWDER|FLOUR|WAX|BUTTER|GUM|RESIN)$')
# 복합 반응물·발효 산물은 식물 이름이 등장해도 단일 식물 유래로 승격하지 않는다.
EXCLUDED = re.compile(r'\b(FERMENT\w*|PEG|PPG|COPOLYMER|CROSSPOLYMER|ESTER\w*|ETHER\w*|QUATERNIUM\w*|SILICONE\w*|SILOXANE\w*|SILAN\w*|ANIMAL|BOVINE|PORCINE|FISH|EGG|MILK)\b|\b\w+(?:OYL|YL)\b')
BOTANICAL_ACTION = re.compile(r'\b(extract|extracted|expressed|distillate|distillation|powder|dried|oil|juice|wax|gum|resin|flour|butter)\b', re.I)


def evidence_rule(name, definition, plant_genera=frozenset()):
    """이름+정의 → 명시적 석유/식물 과·재료/조류·균류 근거 → 분류, 아니면 None."""
    if not definition.strip(): return None
    if re.search(r'\bpetroleum\b|\bcrude oil\b', definition, re.I):
        return '석유계', 'explicit_petroleum', '정의에서 석유 또는 원유에서 얻는 탄화수소/정제 경로를 명시합니다.'
    # 무기염 이름을 구성하는 원소/음이온만 정확히 허용한다. 유기산염은 포함하지 않는다.
    cations=set('SODIUM POTASSIUM CALCIUM MAGNESIUM ZINC ALUMINUM ALUMINIUM IRON FERRIC FERROUS COPPER CUPRIC LITHIUM BARIUM STRONTIUM TITANIUM MANGANESE AMMONIUM'.split())
    anions=set('OXIDE DIOXIDE HYDROXIDE CHLORIDE BROMIDE IODIDE FLUORIDE SULFATE SULPHATE PHOSPHATE CARBONATE BICARBONATE SILICATE BORATE NITRATE NITRITE PEROXIDE PERSULFATE SULFIDE SULPHIDE'.split())
    words=name.upper().split()
    if len(words)==2 and words[0] in cations and words[1] in anions:
        # 정의가 존재하고 해당 원소명도 명시되는 경우에만 분류한다.
        if re.search(r'\b'+re.escape(words[0])+r'\b',definition,re.I):
            return '기타','defined_inorganic_salt','정의에 명시된 무기 원소의 산화물·수산화물·무기염으로 기타에 둡니다. 천연 채굴/합성 여부나 안전성을 정한 것은 아닙니다.'
    families=set(re.findall(r'\b[A-Z][a-z]+aceae\b', definition))
    # 과가 섞이거나 검토하지 않은 생물 과가 등장하면 추론하지 않는다.
    if re.search(r'ferment|reaction product|reacting|ester of|ether of|synthetic fragrance', definition, re.I):
        return None
    if families and SIMPLE_MATERIAL.search(name.upper()) and not EXCLUDED.search(name.upper()) and BOTANICAL_ACTION.search(definition):
        if families <= PLANT_FAMILIES:
            return '식물성', 'botanical_family_material', '정의의 식물 과('+', '.join(sorted(families))+')와 추출·압착·증류 등 원료 형태를 대조했습니다. 용매·담체·제품 전체의 식물성이나 친환경성 보증은 아닙니다.'
        if families <= OTHER_FAMILIES:
            return '기타', 'algae_fungi_family_material', '정의에 명시된 조류·균류의 과('+', '.join(sorted(families))+')에서 얻는 원료로, 이 서비스는 육상 식물과 구분해 기타로 둡니다.'
    botanical = re.fullmatch(r'([A-Z]+) [A-Z]+(?: \([A-Z ]+\))? (?:LEAF|LEAVES|SEED|FRUIT|ROOT|STEM|FLOWER|BARK|PEEL|BRAN|KERNEL|WOOD|BUD|RHIZOME|SPROUT|NEEDLE|HERB|PULP|SHOOT|TUBER|BULB)(?:/(?:LEAF|LEAVES|SEED|FRUIT|ROOT|STEM|FLOWER|BARK|PEEL|BRAN|KERNEL|WOOD|BUD|RHIZOME|SPROUT|NEEDLE|HERB|PULP|SHOOT|TUBER|BULB))* (?:EXTRACT|OIL|WATER|JUICE|POWDER|FLOUR|WAX|BUTTER)', name.upper())
    if (not families and botanical and botanical[1] in plant_genera
            and re.search(r'\b'+re.escape(botanical[1])+r'\b',definition,re.I)
            and re.search(r'\b(?:extract|oil|juice|powder|distillate|distillation|flour|wax|butter)\b.{0,45}\b(?:of|from)\b',definition,re.I)):
        return '식물성', 'referenced_plant_genus_material', '같은 고정 자료에서 육상 식물 과와 연결된 속('+botanical[1]+')을 대조하고, 이 정의에 명시된 해당 식물 부위의 추출·오일 등 원료를 확인했습니다. 추출 용매·담체·완제품의 공급원까지 보증하지 않습니다.'
    if re.search(r'\b(silicone|siloxane)\b', definition, re.I) and re.search(r'(?:METHICONE|SILOXANE|SILICONE|SILSESQUIOXANE)', name.upper()):
        return '기타', 'defined_silicone_family', '정의에서 실리콘/실록세인계 구조로 확인되어 기타에 둡니다. 복합 전구체 전체의 공급원이나 생분해성을 정한 것은 아닙니다.'
    return None


def base_database(root):
    with TemporaryDirectory(prefix='origin-base-') as folder:
        target=Path(folder)
        shutil.copytree(root/'data',target/'data',ignore=shutil.ignore_patterns('origin_*.csv','origin_*.json'))
        return load_ingredients(target)


def extract(root, cache):
    database=base_database(root)
    path=get_source(cache, SOURCES['cosing'])
    entries=[];seen={}
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as connection:
        source_rows=connection.execute('SELECT Ref_No, trim(INCI_name), trim(Chem_Name), trim(Function) FROM cosing ORDER BY Ref_No').fetchall()
        genera={}
        for taxonomy_ref,name,definition,_ in source_rows:
            families=set(re.findall(r'\b[A-Z][a-z]+aceae\b',definition))
            genus=re.match(r'^([A-Z]+) [A-Z]+(?: |$)',name.upper())
            if genus and genus[1] not in {'HYDROLYZED','HYDROGENATED','OXIDIZED','ACETYLATED','SODIUM','POTASSIUM','CALCIUM','MAGNESIUM','LACTOBACILLUS','SACCHAROMYCES','BACILLUS'} and families and families <= PLANT_FAMILIES and SIMPLE_MATERIAL.search(name.upper()) and not EXCLUDED.search(name.upper()):
                genera.setdefault(genus[1],str(taxonomy_ref))
        for ref,name,definition,functions in source_rows:
            record=database.find(name)
            if not record or record.origin!='확인 필요':continue
            rule=evidence_rule(name,definition,genera)
            if rule is None:continue
            origin,rule_id,explanation=rule
            if record.name in seen:
                if seen[record.name]!=origin:raise ValueError('동일 성분의 상충 근거: '+record.name)
                continue
            seen[record.name]=origin
            entries.append(dict(name=record.name,source_name=name,source_ref=str(ref),origin=origin,rule=rule_id,
                                evidence_summary=explanation,definition_sha256=hashlib.sha256(definition.encode()).hexdigest(),
                                functions=functions,checked_on=CHECKED_ON,
                                taxonomy_ref=genera.get(name.split()[0].upper(),'') if rule_id=='referenced_plant_genus_material' else ''))
    review={'format_version':1,'policy_version':1,'checked_on':CHECKED_ON,'source':SOURCES['cosing'],
            'source_date':'2019-03-16','method':'고정 정의에서 검토한 명시적 규칙 대조. 개별 최신 수동 검토/제조사 공급원 인증이 아님.',
            'plant_families':sorted(PLANT_FAMILIES),'other_families':sorted(OTHER_FAMILIES),'entries':entries}
    (root/'data/reviewed/origin_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return review


def build(root=ROOT):
    database=base_database(root);data=root/'data'
    review=json.loads((data/'reviewed/origin_review.json').read_text(encoding='utf-8'))
    entries=[];seen=set();origins=Counter(database.origin_counts)
    for item in review['entries']:
        record=database.find(item['name'])
        if record is None or record.origin!='확인 필요' or record.name in seen:raise ValueError('기본 자료와 유래 검토 대상 불일치')
        seen.add(record.name)
        if item['origin'] not in {'식물성','석유계','기타'}:raise ValueError('검토 유래 오류')
        origins['확인 필요']-=1;origins[item['origin']]+=1
        entries.append(dict(name=record.name,aliases='|'.join(record.aliases),origin=item['origin'],
            reason='2019 CosIng 비공식 스냅샷 정의의 규칙 대조, Ref '+item['source_ref']+': '+item['evidence_summary']+' 최신 규제·안전성 검토나 제품 배치 공급원 인증은 아닙니다.',
            functions='|'.join(record.functions or tuple(x.strip() for x in item['functions'].split(',') if x.strip())),
            source_url=SOURCES['cosing']['source_url'],checked_on=item['checked_on'],uncertainty_reason=''))
    route_review=json.loads((data/'reviewed/origin_route_review.json').read_text(encoding='utf-8'))
    for item in route_review['entries']:
        record=database.find(item['name'])
        if record is None or record.origin!='확인 필요' or record.name in seen:
            raise ValueError('제조 경로 참고 자료의 대상 불일치')
        seen.add(record.name)
        entries.append(dict(name=record.name,aliases='|'.join(record.aliases),origin='확인 필요',
            reason='[제조 경로 참고] '+item['summary']+' 과거 제조 자료의 요약이며 현재 규제·안전성 평가가 아닙니다.',
            functions='|'.join(record.functions),source_url=item['source_url'],checked_on=item['checked_on'],uncertainty_reason='origin_uncertain'))
    write_csv(data/'origin_ingredients.csv',list(entries[0]),entries)
    promoted=sum(database.find(i['name']).uncertainty_reason=='evidence_insufficient' for i in review['entries'])
    manifest={'format_version':1,'policy_version':1,'checked_on':review['checked_on'],'source_date':review['source_date'],
              'method':review['method'],'source':review['source'], 'classified_records':len(review['entries']),'route_reference_records':len(route_review['entries']),'overlay_records':len(entries),
              'rule_counts':dict(Counter(i['rule'] for i in review['entries'])),
              'added_origin_counts':dict(Counter(i['origin'] for i in review['entries'])),
              'merged_records':len(database.records),'merged_origin_counts':dict(origins),
              'merged_curated_count':database.curated_count+promoted,'merged_registry_count':database.registry_count-promoted,
              'base_files':{n:hashlib.sha256((data/n).read_bytes()).hexdigest() for n in ['ingredients.csv','ingredient_names.csv','sources.json','kcia_sources.json']},
              'files':{n:hashlib.sha256((data/n).read_bytes()).hexdigest() for n in ['origin_ingredients.csv','reviewed/origin_review.json','reviewed/origin_route_review.json']}}
    (data/'origin_sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--extract',action='store_true');parser.add_argument('--cache',type=Path,default=ROOT/'.cache/ingredient-sources');a=parser.parse_args()
    if a.extract:
        a.cache.mkdir(parents=True,exist_ok=True);extract(ROOT,a.cache)
    m=build();print({k:m[k] for k in ['classified_records','added_origin_counts','merged_origin_counts','merged_curated_count']})
