"""사용자가 제공한 실사진을 로컬 CPU로 검사한다. 정답은 추론 후 평가에만 사용한다.

python -m scripts.check_real_ocr --workers 2
python -m scripts.check_real_ocr --results-only artifacts/real-before --report artifacts/before-report.json
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import re
import time

from core.database import ROOT, load_ingredients
from core.normalize import clean_ocr_fragment, normalize_key


def fingerprint():
    digest = hashlib.sha256()
    for path in sorted([*ROOT.glob('core/*.py'), *ROOT.glob('features/*.py'),
                        *ROOT.glob('data/*.csv'), ROOT/'scripts/ocr_downloads.py']):
        digest.update(path.name.encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


def _initialize():
    global _engine
    from core.ocr import OCREngine
    _engine = OCREngine()


def _recognize(task):
    from features.recognition import recognize_photo
    name, sample_root, output, revision = task
    source = Path(sample_root)/name
    started = time.monotonic()
    data = source.read_bytes()
    try:
        result = recognize_photo(data, source.name, engine=_engine)
        record = {'file': name, 'sha256': hashlib.sha256(data).hexdigest(),
                  'seconds': time.monotonic()-started, 'fingerprint': revision,
                  'environment': f'{platform.system()} Python {platform.python_version()} CPU',
                  'scan': asdict(result.result)}
        result.image.save(Path(output)/(source.stem+'.selected.jpg'))
    except Exception as exc:
        record = {'file':name, 'sha256':hashlib.sha256(data).hexdigest(),
                  'seconds':time.monotonic()-started, 'fingerprint':revision,
                  'exception':type(exc).__name__, 'message':str(exc)}
    (Path(output)/(source.stem+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return name, record.get('scan',{}).get('status',record.get('exception')), record['seconds']


def _name_key(value, database):
    cleaned, _ = clean_ocr_fragment(value)
    # 評価의 대상은 성분명이다. 숫자/슬래시/nano는 보존하고 완전한 함량 주석만 제외한다.
    cleaned = re.sub(r'\(\s*[\d,.]+\s*(?:ppm|ppb|%)\s*\)', '', cleaned, flags=re.I).strip()
    record = database.find(cleaned)
    return normalize_key(record.name if record else cleaned)


def metrics(expected, predicted):
    expected, predicted = set(expected), set(predicted)
    true = expected & predicted
    precision = len(true)/len(predicted) if predicted else 0.
    recall = len(true)/len(expected) if expected else 0.
    return {'correct':len(true),'expected':len(expected),'predicted':len(predicted),
            'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0.,
            'missing':sorted(expected-predicted),'extra':sorted(predicted-expected)}


def evaluate(photos, sample_root, results):
    database = load_ingredients()
    rows = []
    for photo in photos:
        path = results/(Path(photo['file']).stem+'.json')
        if not path.exists():
            rows.append({'file':photo['file'],'group':photo['group'],'view':photo['view'],'status':'not_run'})
            continue
        record = json.loads(path.read_text(encoding='utf-8'))
        if record['sha256'] != photo['sha256']:
            raise ValueError(f"사진과 결과의 SHA가 다릅니다: {photo['file']}")
        expected = [_name_key(s,database) for s in (sample_root/photo['expected']).read_text(encoding='utf-8').splitlines() if s.strip()]
        scan = record.get('scan',{})
        items = scan.get('ingredients',[])
        proposed = [_name_key(d['name'],database) for d in items]
        raw = [_name_key(d['raw_text'],database) for d in items]
        rows.append({'file':photo['file'],'group':photo['group'],'view':photo['view'],
                     'status':scan.get('status',record.get('exception')),'seconds':record['seconds'],
                     'rotation':scan.get('processing',{}).get('rotation'),
                     'fingerprint':record.get('fingerprint','baseline'),
                     'raw_names':metrics(expected,raw),'proposed_names':metrics(expected,proposed),
                     'duplicate_proposals':sum(n-1 for n in Counter(proposed).values()),
                     'note':'제안명은 사용자 확인 전이다. 유사도 점수를 정확도로 세지 않고 정답과 이름이 일치할 때만 적중.'})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples',type=Path,default=ROOT/'samples/ocr')
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/real-final')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--results-only',type=Path)
    parser.add_argument('--workers',type=int,choices=range(1,5),default=1)
    parser.add_argument('--front-only',action='store_true')
    parser.add_argument('--files',nargs='+')
    parser.add_argument('--reuse',action='store_true')
    parser.add_argument('--min-recall',type=float,default=0.)
    parser.add_argument('--min-precision',type=float,default=0.)
    args = parser.parse_args(argv)
    manifest = json.loads((args.samples/'manifest.json').read_text(encoding='utf-8'))
    photos = [p for p in manifest['photos'] if (not args.front_only or p['view']=='front') and (not args.files or p['file'] in args.files)]
    if not photos: parser.error('선택된 사진이 없습니다.')
    results = args.results_only or args.output
    if not args.results_only:
        results.mkdir(parents=True,exist_ok=True)
        revision = fingerprint(); tasks=[]
        for p in photos:
            source = args.samples/p['file']
            if hashlib.sha256(source.read_bytes()).hexdigest()!=p['sha256']: raise ValueError('사진 변경: '+p['file'])
            cached = results/(source.stem+'.json')
            if args.reuse and cached.exists():
                prior=json.loads(cached.read_text(encoding='utf-8'))
                if prior.get('fingerprint')==revision and prior['sha256']==p['sha256']:continue
            tasks.append((p['file'],str(args.samples),str(results),revision))
        with ProcessPoolExecutor(max_workers=args.workers,initializer=_initialize) as pool:
            for future in as_completed([pool.submit(_recognize,task) for task in tasks]):
                name,status,seconds=future.result();print(f'{name}: {status} · {seconds:.1f}s',flush=True)
    rows=evaluate(photos,args.samples,results)
    report=args.report or results/'report.json';report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps({'metric':'중복 제거한 성분명 단위 정확 별칭 대조 precision/recall/F1. raw_names=교정 전, proposed_names=사용자 확인 전 제안.',
                                 'environment':f'{platform.system()} Python {platform.python_version()} CPU','photos':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for row in rows:
        metric=row.get('proposed_names',{})
        print(f"{row['file']}: P={metric.get('precision',0):.1%} R={metric.get('recall',0):.1%} · {row['status']}")
    print('보고서:',report)
    return int(any(r['status']!='ok' or r['proposed_names']['recall']<args.min_recall or r['proposed_names']['precision']<args.min_precision for r in rows))


if __name__=='__main__':raise SystemExit(main())
