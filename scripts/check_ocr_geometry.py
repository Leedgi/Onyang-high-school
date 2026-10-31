"""인공 라벨의 회전/줄마다 다른 곡면을 실제 CPU OCR로 검사. 촬영 사진 정확도 아님."""
from dataclasses import asdict
import json
import time

import cv2
import numpy as np
from PIL import Image

from core.auto_preprocess import Region, prepare_region
from core.database import ROOT, load_ingredients
from core.ocr import OCREngine
from core.scan import scan_ingredients
from scripts.check_auto_ocr import evaluate


def geometry_inputs():
    original=Image.open(ROOT/'tests/fixtures/dense_label.png').convert('RGB')
    # 검사용 인공 라벨을 꽉 채운 별도 합성 입력을 만든다. 앱에서 수동 자르기를 요구하지 않는다.
    _,label,_,_=prepare_region(original,Region((285,758,1270,1003),'heading',32.5,100.))
    padded=Image.new('RGB',(label.width,label.height+200),'white');padded.paste(label,(0,100))
    array=np.asarray(padded);height,width=array.shape[:2]
    y,x=np.mgrid[:height,:width].astype(np.float32);u=x/(width-1)*2-1
    source_x=(np.arcsin(np.clip(u*np.sin(.95),-.999,.999))/.95+1)*.5*(width-1)
    source_y=y-(y-height/2)*.30*u*u
    m1,m2=cv2.convertMaps(source_x.astype(np.float32),source_y.astype(np.float32),cv2.CV_16SC2)
    curved=Image.fromarray(cv2.remap(array,m1,m2,cv2.INTER_CUBIC,borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255)))
    return {'upside_down':(original.transpose(Image.Transpose.ROTATE_180),180),
            'sideways90':(original.transpose(Image.Transpose.ROTATE_90),270),
            'sideways270':(original.transpose(Image.Transpose.ROTATE_270),90),
            'variable_curve':(curved,0),
            'variable_curve180':(curved.transpose(Image.Transpose.ROTATE_180),180)}


def main():
    expected=json.loads((ROOT/'tests/fixtures/dense_label.expected.json').read_text(encoding='utf-8'))['names']
    database=load_ingredients();engine=OCREngine();report={};failed=[]
    folder=ROOT/'artifacts';folder.mkdir(exist_ok=True)
    target=folder/'ocr-geometry-comparison.json'
    for name,(image,rotation) in geometry_inputs().items():
        started=time.monotonic()
        output=scan_ingredients(image,engine,database,progress=lambda s:print(name,s,flush=True))
        result=output.result
        raw=evaluate([d.raw_text for d in result.ingredients],expected,database)
        proposed=evaluate([d.name for d in result.ingredients],expected,database)
        curved=name.startswith('variable_curve')
        ok=(result.status=='ok' and result.processing.get('rotation')==rotation
            and raw['matched']>=(18 if curved else 20) and proposed['matched']>=(20 if curved else 23)
            and proposed['name_precision']>=(.65 if curved else .8)
            and all(not d.confirmed for d in result.ingredients))
        report[name]={'status':result.status,'processing':result.processing,'raw':raw,'unconfirmed_proposals':proposed,
                      'seconds':time.monotonic()-started,'passed':ok,'scan':asdict(result)}
        if not ok:failed.append(name)
        target.write_text(json.dumps({'scope':'기존 인공 라벨에 명시적으로 합성한 회전/곡면. 촬영 사진의 일반 정확도 아님.','cases':report},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('GEOMETRY RESULT',name,'PASS' if ok else 'FAIL','rotation',result.processing.get('rotation'),
              'raw',raw['matched'],'/26','unconfirmed',proposed['matched'],'/26',flush=True)
    if failed:
        print('Failed geometry cases:',', '.join(failed));return 1
    print('Actual CPU rotation/curvature checks passed. Synthetic labels; proposals remain unconfirmed.')
    return 0


if __name__=='__main__':raise SystemExit(main())
