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
