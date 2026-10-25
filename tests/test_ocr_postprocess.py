"""사진에서 읽어 옮긴 라벨과 명시적으로 주입한 OCR 오류의 회귀 검사."""
import json

import pytest

from core.analysis import analyze
from core.database import ROOT, load_ingredients
from core.ingredient_text import heading_span, ingredient_drafts, section_end_span
from core.match import find_candidates
from core.models import ConfirmedIngredient
from core.normalize import clean_ocr_fragment, normalize_text
from core.ocr import parse_output


def lines(texts):
    return parse_output([([[0, i * 40], [1200, i * 40], [1200, i * 40 + 30], [0, i * 40 + 30]], text, .85)
                         for i, text in enumerate(texts)])


@pytest.mark.parametrize('raw', [']정 제 수', '[정 제 수', '】 정\u200b 제\ufeff 수', '］정\u00a0제 수', ']정 제 수 :'])
def test_dangling_bracket_and_spacing_match_without_changing_original(raw):
    match = find_candidates(raw, load_ingredients())
    assert match.status == 'exact'
    assert match.candidates[0].name == '정제수'
    assert match.raw_text == raw
    assert match.transformations
    assert not match.confirmed
    draft = ingredient_drafts(lines([raw]), load_ingredients())[0]
    assert draft.name == '정제수'
    assert draft.original_fragment == raw
    assert draft.raw_text == raw


def test_reuzel_label_all_19_names_survive_spacing_wraps_and_section_markers():
    case = json.loads((ROOT / 'tests/fixtures/reuzel_label_text.json').read_text(encoding='utf-8'))
    ocr = lines(case['noisy_lines'])
    drafts = ingredient_drafts(ocr, load_ingredients())
    assert [d.name for d in drafts] == case['names']
    assert all(d.status == 'exact' and not d.confirmed for d in drafts)
    assert drafts[0].raw_text.startswith(']정 제 수')
    assert drafts[13].source_indices == (4, 5)
    assert '[전 성 분]' in ocr.raw_text
    result = analyze([ConfirmedIngredient(d.name) for d in drafts], load_ingredients(), [])
    assert len(result.rows) == 19
    assert all(r.uncertainty_reason != 'db_missing' for r in result.rows)


@pytest.mark.parametrize('raw', ['[전 성 분] 정 제 수', '【전성분】정제수', '[ 전\u200b 성 분 ]:정제수'])
def test_heading_removes_its_closing_bracket(raw):
    span = heading_span(raw)
    assert span is not None
    assert clean_ocr_fragment(raw[span[1]:])[0].replace(' ', '') == '정제수'
    assert [d.name for d in ingredient_drafts(lines([raw]), load_ingredients())] == ['정제수']


def test_spaced_footer_is_not_an_ingredient():
    raw = '[사 용 상 의 주 의 사 항] 화장품 사용 시'
    assert section_end_span(raw)[0] == 0
    assert len(ingredient_drafts(lines(['[전 성 분] 정 제 수', raw]), load_ingredients())) == 1


def test_unmatched_opening_bracket_does_not_swallow_commas():
    tokens = normalize_text('[정제수, 글리세린, 1,2-헥산다이올')
    assert len(tokens) == 3
    assert tokens[2].name == '1,2-헥산다이올'
    assert [d.name for d in ingredient_drafts(lines(['[정제수, 글리세린, 1,2-헥산다이올']), load_ingredients())] == ['정제수', '글리세린', '1,2-헥산다이올']
    assert len(normalize_text(']1,2-헥산다이올, 정제수')) == 2


@pytest.mark.parametrize('raw', ['티타늄디옥사이드[nano]', '정제수(미등록원료)', '정제수(Water, Glycerin)'])
def test_balanced_qualifiers_and_different_ingredient_annotations_are_preserved(raw):
    assert clean_ocr_fragment(raw)[0] == raw
    assert find_candidates(raw, load_ingredients()).status not in {'exact', 'alias'}


def test_only_verified_same_identity_parenthetical_aliases_can_match():
    match = find_candidates('정 제 수(Water, Aqua)', load_ingredients())
    assert match.status == 'alias'
    assert match.candidates[0].name == '정제수'
    assert 'Water, Aqua' in match.raw_text


def test_fuzzy_candidates_work_after_cleanup_but_are_never_classified_as_exact():
    match = find_candidates('] 미 네 랄 오 일 류', load_ingredients())
    assert match.candidates[0].name == '미네랄오일'
    assert match.candidates[0].method == 'fuzzy'
    assert len(match.candidates) <= 3
    row = analyze([ConfirmedIngredient('] 미 네 랄 오 일 류')], load_ingredients(), []).rows[0]
    assert row.uncertainty_reason == 'db_missing'


def test_confirmed_manual_input_uses_same_format_cleanup():
    raw = '] 정 제 수'
    row = analyze([ConfirmedIngredient(raw)], load_ingredients(), []).rows[0]
    assert row.canonical_name == '정제수'
    assert row.confirmed.name == raw
    assert row.match_method == 'normalized'


def test_hyphen_formatting_changes_but_numeric_identity_does_not():
    database = load_ingredients()
    assert find_candidates('피 이 지/피 피 지－2 5/2 5 다 이 메 티 콘', database).status == 'exact'
    match = find_candidates('폴 리 쿼 터 늄－1 2', database)
    assert match.status not in {'exact', 'alias'}


def test_spaced_numeric_comma_remains_part_of_one_name():
    drafts = ingredient_drafts(lines(['[전성분] ]1, 2 － 헥 산 다 이 올, 정 제 수']), load_ingredients())
    assert [d.name for d in drafts] == ['1,2-헥산다이올', '정제수']


def test_normalized_duplicate_is_counted_once_but_conflicting_amounts_fail():
    database = load_ingredients()
    result = analyze([ConfirmedIngredient('] 정 제 수'), ConfirmedIngredient('정제수')], database, [])
    assert len(result.rows) == 1
    assert result.duplicates == ('정제수',)
    with pytest.raises(ValueError, match='중복 이름'):
        analyze([ConfirmedIngredient('] 정 제 수', 10), ConfirmedIngredient('정제수', 20)], database, [])
