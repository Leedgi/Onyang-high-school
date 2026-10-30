from dataclasses import replace
import cv2
import numpy as np
from PIL import Image

from core.auto_preprocess import curved_text_variant
from core.database import load_ingredients
from core.models import OCRResult
from core.ocr import parse_output
from core.scan import scan_ingredients
import core.scan as scan


def output(text, confidence=.8):
    return parse_output([([(10,20),(360,20),(360,45),(10,45)],text,confidence)])


class FakeEngine:
    """명시적 모의 OCR. 사진 정확도 측정에 쓰지 않는다."""
    def __init__(self, coarse):
        self.results=coarse
        self.calls=0

    def recognize(self,image,reading_order='rows',*,accurate=False):
        if accurate:
            return output('정제수, 글리세린, 미네랄오일')
        result=self.results[self.calls]
        self.calls+=1
        return result


def test_all_orientations_compared_before_false_initial_heading_wins(monkeypatch):
    monkeypatch.setattr(scan,'refine_words',lambda image,ocr,drafts,*args:(drafts,()))
    engine=FakeEngine([output('전성분: 정제수',.99), output('전성분: 정제수, 글리세린, 미네랄오일'),
                       output('정제수'), OCRResult('empty')])
    result=scan_ingredients(Image.new('RGB',(400,200),'white'),engine,load_ingredients())
    assert engine.calls==4
    assert result.result.processing['rotation']==180
    assert [p['rotation'] for p in result.result.passes[:4]]==[0,180,90,270]
    assert result.result.status=='ok'
    assert all(not d.confirmed for d in result.result.ingredients)


def test_one_orientation_execution_failure_does_not_abort_remaining_angles(monkeypatch):
    monkeypatch.setattr(scan,'refine_words',lambda image,ocr,drafts,*args:(drafts,()))
    engine=FakeEngine([OCRResult('execution_error',message='test angle failure'),
                       output('전성분: 정제수, 글리세린, 미네랄오일'),OCRResult('empty'),OCRResult('empty')])
    result=scan_ingredients(Image.new('RGB',(400,200),'white'),engine,load_ingredients())
    assert engine.calls==4 and result.result.status=='ok'
    assert result.result.processing['rotation']==180
    fatal=FakeEngine([OCRResult('model_error',message='test model failure')])
    assert scan_ingredients(Image.new('RGB',(400,200),'white'),fatal,load_ingredients()).result.status=='model_error'
    assert fatal.calls==1


def test_curved_alternative_uses_bounded_maps_and_preserves_original():
    arr=np.full((400,800,3),255,np.uint8)
    for y in range(60,361,60):
        for x in range(20,780,20):
            cv2.rectangle(arr,(x,y),(x+9,y+14),(0,0,0),-1)
    yy,xx=np.mgrid[0:400,0:800].astype(np.float32)
    u=xx/799*2-1
    m1,m2=cv2.convertMaps(xx,(yy-18*u*u).astype(np.float32),cv2.CV_16SC2)
    warped=cv2.remap(arr,m1,m2,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255))
    source=Image.fromarray(warped);before=source.tobytes()
    corrected,meta=curved_text_variant(source,30)
    assert source.tobytes()==before and corrected.size==source.size
    assert meta['curve_detected'] and meta['supporting_rows']>=3
    assert 0 < meta['max_vertical_shift'] <= 17
    def drift(image):
        a=np.array(image).mean(axis=2)
        def position(x):
            profile=(255-a[50:95,max(0,x-20):x+20]).mean(axis=1)
            return np.argmax(profile)
        return abs(int(position(70))-int(position(400)))
    assert drift(corrected)<drift(source)
