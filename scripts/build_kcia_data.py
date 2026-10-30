"""공개 명칭 사실과 별도 검토 입력에서 KCIA 확장 자료를 오프라인 생성한다."""
from collections import Counter
from dataclasses import replace
import csv
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from core.database import ROOT, load_ingredients
from core.models import IngredientRecord
from core.normalize import normalize_key


def write_csv(path, fields, rows):
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)


def base_database(root):
    # 확장 자료 자체를 다시 입력으로 읽지 않도록 기존 출처만 별도 임시 폴더에서 읽는다.
    with TemporaryDirectory(prefix='ingredient-base-') as folder:
        target=Path(folder);(target/'data').mkdir()
        for name in ['ingredients.csv','ingredient_names.csv','sources.json','caution_aliases.csv']:
            source=root/'data'/name
            if source.exists():shutil.copy2(source,target/'data'/name)
        return load_ingredients(target)


def build(root=ROOT):
    data=root/'data'
    metadata=json.loads((data/'reviewed/kcia_source_input.json').read_text(encoding='utf-8'))
    if hashlib.sha256((data/'kcia_standard_names.csv').read_bytes()).hexdigest()!=metadata['names_sha256']:
        raise ValueError('검토한 명칭 목록 체크섬과 일치하지 않습니다.')
    with (data/'kcia_standard_names.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    if len(rows)!=metadata['source_rows'] or len({r['kcia_id'] for r in rows})!=len(rows):
        raise ValueError('명칭 목록의 누락·중복을 확인해 주세요.')
    review=json.loads((data/'reviewed/kcia_origin_review.json').read_text(encoding='utf-8'))
    reviewed={r['kcia_id']:r for r in review['entries']}
    original=base_database(root)
    records=list(original.records);base_size=len(records)
    name_only=set(range(original.curated_count,base_size))
    index={normalize_key(n):i for i,r in enumerate(records) for n in (r.name,*r.aliases)}
    touched=set();conflicts=[];origin_changes=[];resolved={};reviewed_positions=set()
    for row in rows:
        names=list(dict.fromkeys(n.strip() for n in [row['name'],row['inci'],row['old_name'],row['old_inci']] if n.strip()))
        names=[n for n in names if '|' not in n]
        if not names:raise ValueError('빈 명칭 행')
        # 우선 공식 현/구 INCI를 대조한다. 근접 이름이나 숫자를 삭제한 이름으로 합치지 않는다.
        position=next((index[normalize_key(n)] for n in [row['inci'],row['old_inci']] if n and normalize_key(n) in index),None)
        if position is None and not row['inci']:
            position=index.get(normalize_key(row['name']))
        if position is None:
            canonical=row['inci'] or row['name']
            position=index.get(normalize_key(canonical))
            if position is None:
                position=len(records)
                records.append(IngredientRecord(canonical,(),'확인 필요',
                    '대한화장품협회 공개 표준화 명칭 목록(2026-09-30)의 이름 연결입니다. 공개 정의·원료 제조 경로를 별도 검토하지 않은 항목이므로 유래·사용 허용·안전성을 확정하지 않습니다.',
                    source_url=metadata['source_url']+'#page='+row['page'],checked_on=metadata['checked_on'],uncertainty_reason='evidence_insufficient'))
                index[normalize_key(canonical)]=position;name_only.add(position)
        aliases=list(records[position].aliases)
        for name in names:
            key=normalize_key(name)
            if key in index and index[key]!=position:
                conflicts.append(dict(kcia_id=row['kcia_id'],alias=name,target=records[position].name,
                                      existing=records[index[key]].name,reason='기존 다른 레코드와 연결되므로 자동 병합에서 제외'))
                continue
            if key not in index:
                aliases.append(name);index[key]=position
        record=replace(records[position],aliases=tuple(aliases))
        if row['kcia_id'] in reviewed:
            item=reviewed[row['kcia_id']]
            if normalize_key(item['inci'])!=normalize_key(row['inci']) or not item['definition_reviewed']:
                raise ValueError('검토 정의와 명칭이 다릅니다: '+row['kcia_id'])
            if position in reviewed_positions and record.origin!=item['origin']:
                raise ValueError('같은 성분에 서로 다른 검토 유래: '+record.name)
            if record.origin!=item['origin']:
                origin_changes.append(dict(kcia_id=row['kcia_id'],name=record.name,before=record.origin,after=item['origin']))
            record=replace(record,origin=item['origin'],reason='KCIA 공개 기원 및 정의를 바탕으로 한 본 사이트의 분류입니다. '+item['reason'],
                           functions=tuple(item['functions']),source_url=item['source_url'],checked_on=item['checked_on'],
                           uncertainty_reason='origin_uncertain' if item['origin']=='확인 필요' else '')
            name_only.discard(position);reviewed_positions.add(position)
        records[position]=record;touched.add(position);resolved[row['kcia_id']]=record.name
    overlay=[records[i] for i in sorted(touched) if i>=base_size or records[i]!=original.records[i]]
    entries=[dict(name=r.name,aliases='|'.join(r.aliases),origin=r.origin,reason=r.reason,functions='|'.join(r.functions),
                  source_url=r.source_url,checked_on=r.checked_on,uncertainty_reason=r.uncertainty_reason) for r in overlay]
    write_csv(data/'kcia_ingredients.csv',list(entries[0]),entries)
    write_csv(data/'kcia_import_conflicts.csv',['kcia_id','alias','target','existing','reason'],conflicts)
    manifest={'format_version':1,**metadata,
              'base_files':{name:hashlib.sha256((data/name).read_bytes()).hexdigest()
                            for name in ['ingredients.csv','ingredient_names.csv','sources.json']},
              'source_definition_reviews':len(reviewed),
              'reviewed_unique_records':len(reviewed_positions),'review_origin_counts':dict(Counter(r['origin'] for r in reviewed.values())),
              'overlay_records':len(overlay),'added_records':len(records)-base_size,
              'merged_records':len(records),'merged_curated_count':len(records)-len(name_only),
              'merged_registry_count':len(name_only),'merged_lookup_keys':len(index),
              'merged_origin_counts':dict(Counter(r.origin for r in records)),
              'excluded_conflicting_aliases':len(conflicts),'origin_changes':origin_changes,
              'reviewed_targets':{key:resolved[key] for key in reviewed},
              'files':{name:hashlib.sha256((data/name).read_bytes()).hexdigest() for name in
                       ['kcia_standard_names.csv','kcia_ingredients.csv','kcia_import_conflicts.csv','reviewed/kcia_origin_review.json','reviewed/kcia_source_input.json']}}
    (data/'kcia_sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    m=build();print({k:m[k] for k in ['source_rows','overlay_records','added_records','merged_records','merged_curated_count','merged_lookup_keys','excluded_conflicting_aliases']})
