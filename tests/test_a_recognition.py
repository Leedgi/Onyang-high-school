import pytest

from features.recognition import prepare_review, recognize_photo


def test_review_normalizes_format_and_keeps_uncertain_candidates():
    drafts = prepare_review("]정 제 수, 폴 리 쿼 터 늄－1 1, 미네활오잃")
    assert [d.name for d in drafts[:2]] == ["정제수", "폴리쿼터늄-11"]
    assert drafts[2].status == "needs_review"
    assert drafts[2].candidates[0].name == "미네랄오일"
    assert all(not d.confirmed for d in drafts)
    assert drafts[0].original_fragment == "]정 제 수"


def test_invalid_photo_fails_before_engine_is_used():
    with pytest.raises(ValueError, match="빈 파일"):
        recognize_photo(b"", "label.jpg", engine=object())


def test_empty_review_has_no_fabricated_names():
    assert prepare_review("") == ()
