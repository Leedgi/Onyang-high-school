from core.analysis import analyze
from core.database import IngredientDatabase
from core.models import ConfirmedIngredient, IngredientRecord


def test_automatic_estimates_only_detail_origin_and_preserves_known_unknowns():
    reference=IngredientRecord('ABCDX OIL',(), '식물성', '등록 근거',detail_origin='식물 유래',source_url='https://example.org/source',checked_on='2026-01-01',detail_confidence='테스트 근거',detail_reason='인공 자료',detail_source_url='https://example.org/source')
    unknown=IngredientRecord('ABCDY OIL',(), '확인 필요', '여러 제조 경로',uncertainty_reason='origin_uncertain',detail_origin='확인 필요',source_url='https://example.org/source',checked_on='2026-01-01',detail_confidence='테스트 근거',detail_reason='인공 자료',detail_source_url='https://example.org/source')
    db=IngredientDatabase([reference,unknown],'real')
    manual=analyze([ConfirmedIngredient(unknown.name)],db,[])
    assert manual.rows[0].detail_origin=='확인 필요'
    auto=analyze([ConfirmedIngredient(unknown.name),ConfirmedIngredient('완전미등록원료')],db,[],automatic=True)
    assert len(auto.rows)==1 and auto.count_ratio.denominator==1
    assert auto.rows[0].detail_origin=='식물 유래' and auto.rows[0].detail_is_estimate
    assert auto.rows[0].origin=='확인 필요' and auto.rows[0].reason=='여러 제조 경로'
    assert auto.rows[0].confirmed.amount is None
    assert len(auto.automatic_decisions)==1 and not auto.automatic_decisions[0].selected_name


def test_automatic_does_not_invent_origin_without_similar_reference():
    db=IngredientDatabase([IngredientRecord('전혀다른물질',(),'확인 필요','근거 없음',uncertainty_reason='origin_uncertain',source_url='https://example.org/source',checked_on='2026-01-01',detail_confidence='테스트 근거',detail_reason='인공 자료',detail_source_url='https://example.org/source')],'real')
    result=analyze([ConfirmedIngredient('전혀다른물질')],db,[],automatic=True)
    assert len(result.rows)==1 and result.rows[0].origin=='확인 필요'
