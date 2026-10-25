"""정확·별칭·RapidFuzz 후보. 검색 결과를 분석용 성분으로 자동 확정하지 않는다."""
from dataclasses import dataclass
from pathlib import Path
import math
import tomllib
import re

from rapidfuzz.fuzz import ratio
from rapidfuzz import process

from core.database import IngredientDatabase, ROOT
from core.models import Candidate, MatchResult
from core.normalize import normalize_key, clean_ocr_fragment, normalize_text


@dataclass(frozen=True)
class MatchSettings:
    min_score: float = 60.0
    ambiguous_gap: float = 5.0
    max_candidates: int = 3

    def __post_init__(self):
        if not math.isfinite(self.min_score) or not 0 <= self.min_score <= 100:
            raise ValueError("유사도 임계값은 0~100이어야 합니다.")
        if not math.isfinite(self.ambiguous_gap) or not 0 <= self.ambiguous_gap <= 100:
            raise ValueError("후보 점수 차이 기준은 0~100이어야 합니다.")
        if type(self.max_candidates) is not int or not 1 <= self.max_candidates <= 3:
            raise ValueError("이름 후보는 1~3개만 제시할 수 있습니다.")


def load_match_settings(path: Path = ROOT / "config.toml") -> MatchSettings:
    try:
        with path.open("rb") as file:
            return MatchSettings(**tomllib.load(file)["matching"])
    except (KeyError, TypeError) as exc:
        raise ValueError("config.toml의 matching 설정과 항목 이름을 확인해 주세요.") from exc


def find_candidates(raw_text: str, database: IngredientDatabase, settings: MatchSettings | None = None) -> MatchResult:
    settings = settings or MatchSettings()
    cleaned, changes = clean_ocr_fragment(raw_text)
    parenthetical = re.fullmatch(r"(.+?)\s*\(([^()]*)\)", cleaned)
    parenthetical_record = None
    if parenthetical:
        outer = database.find(parenthetical[1].strip())
        inner = normalize_text(parenthetical[2])
        if outer and inner and all(database.find(token.name) == outer for token in inner):
            parenthetical_record = outer
            cleaned = outer.name
            changes = (*changes, "같은 성분으로 확인된 괄호 속 별칭 정리")
    if any(char.isspace() for char in cleaned):
        changes = (*changes, "성분 대조 시 공백 제외")
    query = normalize_key(cleaned)
    def result(status, candidates, gap=None):
        return MatchResult(raw_text, query, status, tuple(candidates), gap,
                           cleaned_text=cleaned, transformations=changes)
    if not query:
        return result("no_candidates", ())
    direct = database.find(cleaned)
    if direct:
        exact = normalize_key(direct.name) == query and parenthetical_record is None
        matched = direct.name if exact or parenthetical_record else next(alias for alias in direct.aliases if normalize_key(alias) == query)
        method = "exact" if exact else "alias"
        return result(method, (Candidate(direct.name, matched, method, 100.0),))
    # 많은 INCI 이름도 C 구현으로 한 번에 비교한다. 같은 정식명의 별칭은 최고 점수로 묶는다.
    best = {}
    for key, score, _ in process.extract(query, database.index.keys(), scorer=ratio, score_cutoff=settings.min_score, limit=None):
        record = database.index[key]
        if record.name not in best:
            matched_name = next(name for name in (record.name, *record.aliases) if normalize_key(name) == key)
            best[record.name] = Candidate(record.name, matched_name, "fuzzy", float(score))
    ranked = list(best.values())
    ranked.sort(key=lambda candidate: (-candidate.score, candidate.name))
    # 최대 표시 개수 밖의 다음 후보도 비교해 동점을 숨기지 않는다.
    gap = ranked[0].score - ranked[1].score if len(ranked) > 1 else None
    if not ranked:
        status = "no_candidates"
    elif gap is not None and math.isclose(gap, 0, abs_tol=1e-9):
        status = "tie"
    elif gap is not None and gap < settings.ambiguous_gap:
        status = "ambiguous"
    else:
        status = "fuzzy"
    return result(status, ranked[:settings.max_candidates], gap)
