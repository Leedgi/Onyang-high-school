"""기하·후처리와 실패 분기 회귀. 모의 인식 결과를 사진 정확도로 사용하지 않는다."""
import cv2
import numpy as np
from PIL import Image

from core.auto_preprocess import rectified_text_rows
from core.database import load_ingredients
from core.ingredient_text import ingredient_drafts
from core.models import IngredientDraft, OCRResult
from core.ocr import parse_output
from core.scan import scan_ingredients
from core.word_refine import refine_words


def output(text, y=10):
    return parse_output([([(10,y),(900,y),(900,y+36),(10,y+36)],text,.9)])


def test_separator_only_ocr_lines_do_not_crash_or_create_ingredients():
    blocks=[]
    for i,text in enumerate(['전 성 분: 정 제 수',',','글 리 세 린',';','향료']):
        blocks.append(([(10,i*50),(900,i*50),(900,i*50+30),(10,i*50+30)],text,.8))
    ocr=parse_output(blocks)
    drafts=ingredient_drafts(ocr,load_ingredients())
    assert [d.name for d in drafts]==['정제수','글리세린','향료']
    assert ocr.raw_text.count(',')==1
    assert all(not d.confirmed for d in drafts)


def test_unique_one_letter_proposal_preserves_raw_and_numeric_identity():
    db=load_ingredients()
    d=ingredient_drafts(output('소 듬 하 이 드 록 사 이 드'),db)[0]
    assert d.name=='소듐하이드록사이드' and d.status=='correction_proposed'
    assert d.raw_text=='소 듬 하 이 드 록 사 이 드' and not d.confirmed
    wrong=ingredient_drafts(output('피이지-101스테아레이트'),db)[0]
    assert wrong.name!='피이지-100스테아레이트'


def test_precise_orientation_fallback_recovers_180_when_locator_has_no_text(monkeypatch):
    import core.scan as scan
    monkeypatch.setattr(scan,'refine_words',lambda image,ocr,drafts,*args:(drafts,()))
    class Engine:
        def __init__(self):self.coarse=0;self.accurate=0
        def recognize(self,image,reading_order='rows',*,accurate=False):
            if not accurate:self.coarse+=1;return OCRResult('empty')
            self.accurate+=1
            if self.accurate in [1,3,4]:return OCRResult('empty')
            return output('전성분: 정제수, 글리세린, 미네랄오일')
    engine=Engine()
    result=scan_ingredients(Image.new('RGB',(1000,140),'white'),engine,load_ingredients())
    assert engine.coarse==4 and result.result.status=='ok'
    assert result.result.processing['rotation']==180
    assert any(p.get('stage')=='orientation_refine' for p in result.result.passes)


def test_row_tracking_handles_opposite_bows_and_a_short_final_line():
    source=np.full((550,1200,3),255,np.uint8)
    for i,y in enumerate([90,160,230,300,370,440]):
        for x in range(60,180 if i==5 else 1140,30):
            cv2.rectangle(source,(x,y),(x+15,y+24),(0,0,0),-1)
    yy,xx=np.mgrid[:550,:1200].astype(np.float32);u=xx/1199*2-1
    m1,m2=cv2.convertMaps(xx,(yy-(yy-275)*.25*u*u).astype(np.float32),cv2.CV_16SC2)
    warped=Image.fromarray(cv2.remap(source,m1,m2,cv2.INTER_CUBIC,borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255)))
    before=warped.tobytes();rows,metadata=rectified_text_rows(warped,36)
    assert warped.tobytes()==before and len(rows)==6
    assert metadata['rows_in_source_image'][-1]['support']<metadata['rows_in_source_image'][0]['support']
    a=np.asarray(rows[0]).mean(axis=2);centers=[]
    for x in range(50,a.shape[1]-50,60):
        ink=np.maximum(200-a[:,x:x+30],0);weights=ink.sum(axis=1)
        if weights.sum()>100:centers.append(float(np.dot(np.arange(len(weights)),weights)/weights.sum()))
    assert np.std(centers)<4


def test_two_engine_pixel_consensus_remains_an_unconfirmed_proposal():
    db=load_ingredients()
    raw='펜타에리스리틸테트라-다이-ㄴ부틸하이드록시하이드로신나메이트'
    ocr=output(raw);drafts=ingredient_drafts(ocr,db)
    class Engine:
        def recognize_line(self,image):return output(raw)
        def recognize(self,image,*args,**kwargs):return output('팬타에리스리틸테트라-다이-t-부틸하이드록시하이드로신나메이트')
    result,passes=refine_words(Image.new('RGB',(1000,80),'white'),ocr,drafts,Engine(),db,lambda _:None)
    assert result[0].name=='펜타에리스리틸테트라-다이-t-부틸하이드록시하이드로신나메이트'
    assert result[0].status=='ai_reread_proposed' and not result[0].confirmed
    assert result[0].raw_text==raw and result[0].original_fragment==raw
    assert passes[0]['two_engine_consensus']


def test_independent_ocr_agreement_does_not_silently_change_numbers():
    raw='1,3-헥산디올';ocr=output(raw)
    draft=IngredientDraft(raw,raw,'needs_review',(0,),original_fragment=raw)
    class Engine:
        def recognize_line(self,image):return output('1,2-헥산다이올')
        def recognize(self,image,*args,**kwargs):return output('1,2-헥산다이올')
    result,passes=refine_words(Image.new('RGB',(1000,80),'white'),ocr,(draft,),Engine(),load_ingredients(),lambda _:None)
    assert result==(draft,) and not passes[0]['applied_as_unconfirmed_proposal']


def test_weak_false_heading_does_not_outscore_precise_upright_evidence(monkeypatch):
    import core.scan as scan
    monkeypatch.setattr(scan,'refine_words',lambda image,ocr,drafts,*args:(drafts,()))
    class Engine:
        def __init__(self):self.coarse=0;self.precise=0
        def recognize(self,image,reading_order='rows',*,accurate=False):
            if not accurate:
                self.coarse+=1
                if self.coarse==1:
                    r=output('전성분: 정제수')
                    from dataclasses import replace
                    return replace(r,blocks=tuple(replace(b,confidence=.99) for b in r.blocks))
                return OCRResult('empty')
            self.precise+=1
            if self.precise in (1,3,4):return OCRResult('empty')
            return output('전성분: 정제수, 글리세린, 미네랄오일')
    result=scan_ingredients(Image.new('RGB',(1000,140),'white'),Engine(),load_ingredients())
    assert result.result.status=='ok' and result.result.processing['rotation']==180
