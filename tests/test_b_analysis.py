import pytest

from core.database import load_ingredients
from features.analysis import analyze_confirmed
from shared.contracts import AnalysisRequest, ConfirmedIngredient


def test_real_db_and_unknown_denominator():
    database = load_ingredients()
    assert database.curated_count == 270
    assert database.registry_count == 28077
    request = AnalysisRequest(tuple(ConfirmedIngredient(n) for n in ["정제수", "미등록새성분"]))
    result = analyze_confirmed(request)
    assert result.count_ratio.values["확인 필요"] == 50
    assert result.rows[-1].uncertainty_reason == "db_missing"
    assert not any(result.cautions.values())


def test_empty_and_partial_amounts_are_not_reinterpreted():
    assert analyze_confirmed(AnalysisRequest(())).status == "no_data"
    result = analyze_confirmed(AnalysisRequest((ConfirmedIngredient("미네랄오일", 20),
                                               ConfirmedIngredient("시어버터", 8)), "partial"))
    assert result.amount_ratio.values["식물성"] == 8
    assert result.amount_ratio.values["미공개"] == 72
    with pytest.raises(ValueError):
        analyze_confirmed(AnalysisRequest((ConfirmedIngredient("정제수", 120),)))
