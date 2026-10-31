import numpy as np

from core.models import OCRBlock
from core.ocr import NeuralReader, _row_lines
from core.match import find_candidates, matching_request, _request_matches
from core.database import load_ingredients


def test_curved_row_rectangles_do_not_merge_adjacent_full_lines():
    def block(text,y,index):
        return OCRBlock(text,((0,y),(700,y),(700,y+100),(0,y+100)),.9,index)
    # 휨을 포함한 사각형은 겹치지만 두 물리적 인쇄 줄이다.
    rows=_row_lines([block('정제수, 글리세린',0,0),block('판테놀, 향료',42,1)])
    assert [r.raw_text for r in rows]==['정제수, 글리세린','판테놀, 향료']


def test_tiled_reread_keeps_primary_when_overlap_does_not_agree():
    reader=NeuralReader()
    calls=[]
    def read(patch):
        calls.append(patch.shape[1])
        return ('1,3-헥산다이올' if len(calls)==1 else '1,2-헥산다이올') if patch.shape[1]<1000 else '원본 1,3-헥산다이올', .9
    reader.read_line=read
    text,_=reader.read_tiled(np.zeros((30,1400,3),np.uint8))
    assert text=='원본 1,3-헥산다이올'


def test_matching_cache_lives_only_inside_one_request_even_on_failure():
    db=load_ingredients()
    assert _request_matches.get() is None
    try:
        with matching_request():
            a=find_candidates('정 제 수',db)
            assert find_candidates('정 제 수',db) is a
            assert len(_request_matches.get())==1
            raise ValueError('test')
    except ValueError:
        pass
    assert _request_matches.get() is None


def test_quantity_note_is_preserved_while_matching_only_known_name():
    result=find_candidates('쌀겨수(20,000 ppm)',load_ingredients())
    assert result.status in {'exact','alias'}
    assert result.raw_text=='쌀겨수(20,000 ppm)'
    assert any('표시 함량' in step for step in result.transformations)
    for value in ['글리세린(nano)','폴리(C6-14올레핀)','1,3-헥산다이올']:
        match=find_candidates(value,load_ingredients())
        assert not any('표시 함량' in step for step in match.transformations)


def test_only_complete_numeric_safe_names_can_split_at_misread_punctuation():
    from core.ingredient_text import split_known_sequence
    db=load_ingredients()
    assert split_known_sequence('폴리솔베이트80.1.2-헥산다이올',db)==('폴리솔베이트80','1.2-헥산다이올')
    assert split_known_sequence('정제수.알수없는원료',db)==('정제수.알수없는원료',)


def test_short_jamo_correction_is_a_proposal_and_different_digits_are_preserved():
    from core.ingredient_text import ingredient_drafts
    from core.models import OCRResult, OCRLine
    ocr=OCRResult('ok','리모넷, 1,3-헥산다이올',(),(OCRLine('리모넷, 1,3-헥산다이올',()),))
    drafts=ingredient_drafts(ocr,load_ingredients())
    assert drafts[0].raw_text=='리모넷'
    assert drafts[0].name==load_ingredients().find('리모넨').name and drafts[0].status=='correction_proposed'
    assert drafts[1].name=='1,3-헥산다이올'
    assert all(not d.confirmed for d in drafts)


def test_asterisk_footnote_is_not_an_extra_ingredient_and_nano_is_not_removed():
    from core.ingredient_text import ingredient_drafts
    from core.models import OCRResult, OCRLine
    text='리날룰 (*에센셜 오일의 설명입니다.)'
    ocr=OCRResult('ok',text,(),(OCRLine(text,()),))
    drafts=ingredient_drafts(ocr,load_ingredients())
    assert len(drafts)==1 and drafts[0].name==load_ingredients().find('리날룰').name
    assert ocr.raw_text==text
    result=find_candidates('티타늄디옥사이드[nano]',load_ingredients())
    assert 'nano' in result.cleaned_text


def test_generic_ingredient_heading_does_not_capture_product_title():
    from core.ingredient_text import heading_span, section_end_span
    assert heading_span('성분 탐구실 시험 로션') is None
    assert heading_span('성분: 정제수, 글리세린') is not None
    assert heading_span('성분 정제수, 에탄올, 향료') is not None
    assert section_end_span('사용할 때의 주의사항: 원문')[0]==0
