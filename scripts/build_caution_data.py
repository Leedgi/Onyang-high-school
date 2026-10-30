"""검토한 자료만 주의 CSV로 생성한다. 네트워크 접속이나 추정 추가 없음."""
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path

from core.database import load_ingredients
from core.models import CautionRecord
from core.normalize import normalize_key

ROOT = Path(__file__).resolve().parents[1]


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def build(root: Path = ROOT):
    review_path = root / 'data/reviewed/caution_review.json'
    review = json.loads(review_path.read_text(encoding='utf-8'))
    database = load_ingredients(root)
    records, env_rows, seen = [], [], {}
    aliases = []
    for item in review['ingredients']:
        group, inci = item['group'], item['inci']
        evidence = item.get('name_evidence', {})
        if evidence.get('korean_name'):
            names = [evidence['korean_name']]
            if group == 'environment' and evidence.get('old_name'):
                names.append(evidence['old_name'])
            aliases.extend(dict(alias=n, inci=inci, source_url=evidence['source_url'],
                                checked_on=evidence['checked_on'], source_cas=evidence['cas_no']) for n in names)
        source = review['sources'][item['source_id']]
        restriction = '개별 제품의 안전성·사용 허용 판정이 아닙니다. 함량·제품 종류·사용 조건을 확인하세요.'
        use = '해당 성분에 알레르기·감작 이력이 있는 경우 성분표를 확인하고, 증상이 생기면 사용을 중단하고 의료진과 상담하세요.'
        concentration = '제품 함량과 개인 감작 정보가 없어 반응 여부·심각도를 계산하지 않습니다. 보편적인 안전 농도를 제시하지 않습니다.'
        product = '이 성분을 함유한 화장품; 사용 부위·씻어냄 여부 미확인'
        country = '미국 FDA 소비자 안내 (한국 법규 판정 아님)'
        if group == 'aha':
            reason = '[인체·AHA] FDA는 국소 도포 AHA 제품의 자외선 민감성·일광화상 가능성을 안내합니다. 이 성분은 FDA가 열거한 AHA입니다. 각질 제거 정도는 종류·농도·완제품 pH·다른 성분에 따라 달라집니다. (FDA 자료 2022-11-22)'
            use = '국소 도포 AHA 제품을 쓰는 동안과 중단 후 1주 동안 자외선 차단제·보호 의류를 사용하고 햇빛 노출을 제한하라는 FDA 안내입니다. 제품 표시를 따르세요.'
            concentration = '최종 농도·완제품 pH·용도를 알 수 없습니다. 이름 검출만으로 자극성이나 자외선 민감성 증가를 확정하지 않습니다.'
            product = '피부·입술 등 점막에 국소 도포하는 AHA 함유 화장품; 단순 pH 조절 용도인지도 확인 필요'
        elif group == 'bha':
            reason = '[인체·BHA] FDA는 살리실릭애씨드 함유 BHA 화장품 사용 시 자극·오래 지속되는 따가움에 주의하도록 안내합니다. 이 제품이 실제로 자극을 일으킨다는 판정은 아닙니다. (FDA 자료 2022-02-25)'
            use = '라벨의 횟수·방법을 지키고, 넓게 사용하기 전 작은 부위에 확인하세요. 자극·지속되는 따가움이 있으면 중단 후 의료진과 상담하세요. FDA는 영유아·어린이 사용 회피와 자외선 보호를 권고합니다.'
            concentration = '농도·제형·사용 부위를 알 수 없어 개별 제품 영향은 평가하지 않습니다. 이 기록은 한국의 허용 농도 기준이 아닙니다.'
            product = '살리실릭애씨드 함유 BHA 화장품; 의약품 효능·용법 판정 아님'
        elif group in ('fragrance', 'preservative', 'formaldehyde_releaser', 'formaldehyde'):
            kind = {'fragrance':'향료 관련', 'preservative':'보존제', 'formaldehyde_releaser':'포름알데하이드 방출성 원료', 'formaldehyde':'포름알데하이드'}[group]
            reason = f'[인체·알레르기] FDA가 {kind} 알레르겐 목록에 열거한 성분입니다. 일부 소비자에서 알레르기 접촉피부염 등 반응이 생길 수 있습니다. 모든 사람에게 유해하다는 뜻은 아닙니다. (FDA 자료 2026-10-09)'
            if inci == 'LIMONENE':
                reason = '[인체·알레르기] FDA는 d-Limonene을 향료 알레르겐 목록에 열거합니다. INCI LIMONENE에는 여러 이성질체 CAS가 연결되므로 이 표기만으로 d형을 확정하지 않습니다. 원료 확인과 감작 이력 검토를 위한 조건부 안내입니다. (FDA 자료 2026-10-09)'
            if group == 'formaldehyde_releaser':
                concentration += ' 이 성분명만으로 실제 유리 포름알데하이드 양을 계산하지 않습니다.'
        elif group == 'environment':
            record = next(row for row in review['environmental_evidence'] if row['inci'] == inci)
            env_rows.append({**record, 'source_url': source['url'], 'checked_on': source['checked_on']})
            reason = f"[환경·생분해성] PubChem/HSDB에 인용된 {record['test_method']} 시험에서 {record['test_duration_days']}일간 {record['test_result_percent']}% ({record['test_endpoint']})가 보고되어 해당 시험에서 생분해가 제한적이었습니다. 이 수치는 완제품의 분해율이 아닙니다. 자료 시점: {record['source_date_note']}."
            restriction = record['limitations'] + ' 물질의 모든 환경 조건에서 분해가 전혀 일어나지 않는다는 뜻도, 이 제품의 수생 독성·환경 피해를 확정한다는 뜻도 아닙니다.'
            use = '원료 물질/CAS와 시험 조건을 확인하세요. 실제 환경 영향에는 배출량·처리 과정·환경 매체·노출이 필요합니다.'
            concentration = '시험 농도: ' + record['test_concentration'] + ' (제품 함량 아님). 제품의 성분 함량·환경 배출량은 미확인입니다.'
            product = '이 물질을 포함하는 화장품·원료; 혼합물 전체의 생분해 시험은 아님'
            country = '미국 NLM PubChem/HSDB가 정리한 시험 자료 (국가별 규제 판정 아님)'
        else:
            raise ValueError('검토되지 않은 주의 종류')
        targets = list(item['target_names'])
        known = database.find(inci)
        if known:
            targets.append(known.name)
        for target in targets:
            key = normalize_key(target)
            if key in seen:
                if seen[key] != inci:
                    raise ValueError('서로 다른 INCI 사이 표기 충돌: ' + target)
                continue
            seen[key] = inci
            records.append(dict(name=target, reason=reason, restriction=restriction, country=country,
                                product_type=product, use_condition=use, concentration_condition=concentration,
                                source_url=source['url'], checked_on=source['checked_on']))
    write_csv(root / 'data/cautions.csv', list(CautionRecord.__dataclass_fields__), records)
    write_csv(root / 'data/environmental_evidence.csv', list(env_rows[0]), env_rows)
    write_csv(root / 'data/caution_aliases.csv', ['alias','inci','source_url','checked_on','source_cas'], aliases)
    counts = Counter(item['group'] for item in review['ingredients'])
    manifest = {'format_version':1, 'checked_on':review['checked_on'],
                'reviewed_substances':len(review['ingredients']),
                'human_substances':len(review['ingredients'])-len(env_rows),
                'environmental_substances':len(env_rows), 'runtime_name_records':len(records), 'verified_aliases':len(aliases),
                'groups':dict(counts), 'reviewed_input_sha256':hashlib.sha256(review_path.read_bytes()).hexdigest(),
                'files':{n:hashlib.sha256((root/'data'/n).read_bytes()).hexdigest()
                         for n in ['cautions.csv','environmental_evidence.csv','caution_aliases.csv']},
                'sources':review['sources'],
                'scope':'원문을 검토한 30개 물질의 한정 DB. 모든 성분을 포괄하지 않으며 자료 없음은 안전 판정이 아님.'}
    (root/'data/caution_sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__ == '__main__':
    result = build()
    print({k:result[k] for k in ['reviewed_substances','human_substances','environmental_substances','runtime_name_records']})
