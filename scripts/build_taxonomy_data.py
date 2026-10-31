"""검토한 7분류 CSV의 LF·체크섬·집계를 재생성한다. 인터넷 추론/자료 수집은 하지 않는다."""
import csv
import hashlib
import json
from pathlib import Path

from core.database import ROOT

FILES = ('origin_additions.csv','origin_additions_sources.json',
         'origin_additions_round2.csv','origin_additions_round2_sources.json',
         'origin_additions_round3.csv','origin_additions_round3_sources.json',
         'origin_additions_round4.csv','origin_additions_round4_sources.json',
         'caution_additions.csv','caution_additions_sources.json','origin_detail_audit.csv')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root=ROOT):
    data=Path(root)/'data'
    for name in FILES:
        p=data/name
        if p.suffix=='.csv':p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
    for name in FILES:
        if not name.endswith('.csv') or name=='origin_detail_audit.csv':continue
        p=data/name;meta_path=p.with_name(p.stem+'_sources.json')
        meta=json.loads(meta_path.read_text(encoding='utf-8'))
        with p.open(encoding='utf-8-sig',newline='') as f:records=list(csv.DictReader(f))
        meta['sha256']=digest(p);meta['records']=len(records)
        meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    path=data/'origin_taxonomy_sources.json';meta=json.loads(path.read_text(encoding='utf-8'))
    with (data/'origin_detail_audit.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    from collections import Counter
    meta['records']=len(rows);meta['category_counts']=dict(Counter(r['detail_category'] for r in rows));meta['confidence_counts']=dict(Counter(r['confidence'] for r in rows))
    meta['files']={name:digest(data/name) for name in sorted(FILES)}
    base_files=('ingredients.csv','ingredient_names.csv','sources.json','kcia_sources.json','kcia_ingredients.csv',
                'kcia_standard_names.csv','kcia_import_conflicts.csv','origin_ingredients.csv','origin_sources.json')
    meta['base_files']={name:digest(data/name) for name in base_files}
    meta['line_endings']='CSV는 LF로 통일한다. 원본 파일 SHA는 original_import_files에 보존한다.'
    path.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return meta


if __name__=='__main__':
    m=build();print(m['records'],m['category_counts'])
