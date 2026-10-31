from io import BytesIO

from pypdf import PdfReader

from core.database import load_ingredients
from core.models import Candidate, IngredientDraft
from features.analysis import analyze_confirmed
from features.recognition import prepare_review
from shared.contracts import AnalysisRequest, ConfirmedIngredient
from ui.automatic import resolve_automatically
from ui.reporting import build_pdf


def test_excludes_unidentified_and_digit_conflicts_but_keeps_registered_unknown():
    db=load_ingredients()
    wrong=IngredientDraft('1,3-헥산다이올','1,2-헥산다이올','correction_proposed',candidates=(Candidate('1,2-헥산다이올','1,2-헥산다이올','fuzzy',95),))
    junk=IngredientDraft('????','????','unmatched')
    drafts=(*prepare_review('정제수,글리세린'),wrong,junk)
    decisions=resolve_automatically(drafts,db)
    assert [bool(d.selected_name) for d in decisions]==[True,True,False,False]
    r=analyze_confirmed(AnalysisRequest(tuple(ConfirmedIngredient(d.selected_name) for d in decisions if d.selected_name),automatic=True,automatic_decisions=decisions))
    assert len(r.rows)==2 and r.detail_count_ratio.denominator==2
    assert any(x.canonical_name=='글리세린' for x in r.rows)
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(build_pdf(r))).pages)
    assert '미식별 2개 제외' in text and '전체 성분표의 비율이 아닐 수 있습니다' in text
    assert '1,3-헥산다이올' in text


def test_tied_candidates_select_deterministically_without_modifying_draft():
    db=load_ingredients()
    draft=IngredientDraft('글리세런','글리세런','needs_review',candidates=(Candidate('글리세린','글리세린','fuzzy',90),Candidate('글리세롤','글리세롤','fuzzy',90)))
    result=resolve_automatically((draft,),db)[0]
    assert result.selected_name and result.draft is draft and not draft.confirmed
    assert result.score==90 and '자동 추정' in result.reason
