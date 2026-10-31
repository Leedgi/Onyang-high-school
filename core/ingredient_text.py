"""라벨의 물리적 줄과 성분 항목을 구분한다. 분리·교정은 모두 사용자 확인 전 초안이다."""
from collections import defaultdict
from functools import lru_cache
import re
import unicodedata

from rapidfuzz.distance import Levenshtein

from core.database import IngredientDatabase
from core.match import find_candidates, MatchSettings
from core.models import IngredientDraft, OCRResult
from core.normalize import normalize_key, normalize_text, clean_ocr_fragment, search_view

HEADING = re.compile(r"[\[【(〈<]?(?:전성[분문본부]|全成分|(?:full)?ingredients?)[\]】)〉>]?[:：]?", re.I)
SECTION_END = re.compile(
    r"사용\s*(?:기한|방법|법|상의|시\s*주의)|내용량|용량|화장품\s*(?:제조|책임)|제조\s*(?:업자|판매|번호|일)|"
    r"소비자\s*상담|고객\s*(?:상담|센터)|보관\s*방법|주의\s*사항|유통\s*기한|"
    r"made\s*in|expiry|directions|warnings?\b|manufactur|batch\s*(?:no|number)|\([*※]", re.I,
)


def heading_span(text: str) -> tuple[int, int] | None:
    _, compact, positions = search_view(text)
    match = HEADING.search(compact) or re.match(r"[\[【(〈<]?성분(?![은는이가을를의과와])[\]】)〉>]?[:：]?", compact)
    # 긴 광고 문장 중간의 '성분' 같은 단어는 시작 표지로 사용하지 않는다.
    return (positions[match.start()], positions[match.end() - 1] + 1) if match and match.start() <= 8 else None


def section_end_span(text: str) -> tuple[int, int] | None:
    _, compact, positions = search_view(text)
    match = SECTION_END.search(compact)
    if not match:
        return None
    start = match.start()
    if start and compact[start - 1] in "[【(〈<":
        start -= 1
    return positions[start], positions[match.end() - 1] + 1


@lru_cache(maxsize=4)
def _prefix_index(database: IngredientDatabase) -> dict[str, tuple[str, ...]]:
    buckets = defaultdict(list)
    for name in database.index:
        if len(name) >= 2:
            buckets[name[:2]].append(name)
    return {prefix: tuple(sorted(names, key=len, reverse=True)) for prefix, names in buckets.items()}


def split_known_sequence(text: str, database: IngredientDatabase) -> tuple[str, ...]:
    """구분자가 없는 문자열을 전체가 사전 이름으로 덮일 때만 분리한다. 모르는 부분은 버리지 않는다."""
    cleaned, _ = clean_ocr_fragment(text)
    normalized, key, positions = search_view(cleaned)
    if not key or len(key) > 4000 or database.find(text):
        return (cleaned,)
    prefixes = _prefix_index(database)
    best = {0: (0.0, ())}
    for start in range(len(key)):
        if start not in best:
            continue
        score, spans = best[start]
        for word in prefixes.get(key[start:start + 2], ()):
            if not key.startswith(word, start):
                continue
            end = start + len(word)
            candidate = (score + len(word) ** 1.2 - 2, (*spans, (start, end)))
            if end not in best or candidate[0] > best[end][0]:
                best[end] = candidate
    solution = best.get(len(key))
    if solution is None or len(solution[1]) < 2:
        # 점·따옴표를 쉼표로 잘못 읽었어도 양쪽 전체가 검증된 이름 또는
        # 숫자가 같은 한 글자 교정 후보로 덮일 때만 분리 제안한다.
        for boundary in re.finditer(r"[.\u0027]", normalized):
            left, right = normalized[:boundary.start()].strip(), normalized[boundary.end():].strip()
            if not left or not right:
                continue
            a, b = find_candidates(left,database), find_candidates(right,database)
            if (a.status in {"exact","alias"} and
                    (b.status in {"exact","alias"} or _can_propose_spelling(right,b))):
                return left, right
        # 이미지에 실제 공백이 있었을 때만, 한 글자 교정 후보를 포함한 단어 경계도 검토한다.
        # 숫자 변화·동점·알 수 없는 단어는 허용하지 않으며 전체 단어가 덮여야 한다.
        words = list(re.finditer(r"\S+", normalized))
        if not 2 <= len(words) <= 32:
            return (cleaned,)
        word_best = {0: (0.0, ())}
        for start in range(len(words)):
            if start not in word_best:
                continue
            score, spans = word_best[start]
            for end in range(start + 1, min(len(words), start + 8) + 1):
                part = normalized[words[start].start():words[end - 1].end()]
                match = find_candidates(part, database)
                exact = match.status in {"exact", "alias"}
                if not exact and not _plausible_spelling(part, match):
                    continue
                candidate = (score + len(normalize_key(part)) ** 1.2 - (2 if exact else 4), (*spans, part))
                if end not in word_best or candidate[0] > word_best[end][0]:
                    word_best[end] = candidate
        result = word_best.get(len(words))
        return result[1] if result and len(result[1]) >= 2 else (cleaned,)
    return tuple(normalized[positions[start]:positions[end - 1] + 1].strip() for start, end in solution[1])


def _plausible_spelling(raw: str, match) -> bool:
    if not match.candidates:
        return False
    candidate = match.candidates[0]
    query, target = normalize_key(raw), normalize_key(candidate.matched_name)
    return _spelling_eligible(query,target,candidate.score)


def _spelling_eligible(query,target,score):
    # 숫자를 바꾸는 후보는 제안명으로도 대체하지 않는다.
    if re.findall(r"\d+",query)!=re.findall(r"\d+",target):
        return False
    distance=Levenshtein.distance(query,target)
    if len(query)>=5 and score>=80 and distance==1:
        return True
    jamo=Levenshtein.distance(unicodedata.normalize("NFD",query),unicodedata.normalize("NFD",target))
    return ((len(query)>=3 and score>=60 and distance==1 and jamo==1)
            or (len(query)>=8 and score>=80 and distance<=2 and jamo<=2))


def _can_propose_spelling(raw: str, match) -> bool:
    if not _plausible_spelling(raw,match) or match.status not in {"fuzzy","ambiguous"}:
        return False
    query=normalize_key(raw)
    first=match.candidates[0]
    # 긴 이름은 접두사 2~3글자 차이도 유사도 간격이 작다. 한 글자 차이인
    # 첫 후보만 있고 다른 후보가 모두 세 글자 이상 다르면 별도로 검토 제안한다.
    isolated_long=(len(query)>=12 and first.score>=92
                   and Levenshtein.distance(query,normalize_key(first.matched_name))==1
                   and all(Levenshtein.distance(query,normalize_key(c.matched_name))>=3 for c in match.candidates[1:]))
    margin=match.score_gap is None or match.score_gap>=5 or isolated_long
    eligible=sum(_spelling_eligible(query,normalize_key(c.matched_name),c.score) for c in match.candidates)
    return margin and eligible==1


def ingredient_drafts(ocr: OCRResult, database: IngredientDatabase) -> tuple[IngredientDraft, ...]:
    entries = []
    heading_index = next((i for i, line in enumerate(ocr.lines) if heading_span(line.raw_text)), None)
    for i, line in enumerate(ocr.lines):
        if heading_index is not None and i < heading_index:
            continue
        text = line.raw_text
        marker = heading_span(text)
        if marker:
            text = text[marker[1]:]
        end = section_end_span(text)
        if end:
            text = text[:end[0]]
        if text.strip():
            entries.append((text.strip(), line.source_indices))
        if end:
            break
    # 줄바꿈은 제품 라벨의 물리적 배치다. 성분 이름 안에서 끊길 수 있다.
    joined = ""
    source_spans = []
    boundary_proposals = False
    for text, indices in entries:
        separator = " " if joined else ""
        if joined and not joined.rstrip().endswith((",", "，", ";", "；")):
            before = normalize_text(joined)
            after = normalize_text(text)
            previous = before[-1].name if before else ""
            following = after[0].name if after else ""
            previous_match = find_candidates(previous, database)
            previous_complete = previous_match.status in {"exact", "alias"} or _can_propose_spelling(previous, previous_match)
            following_parts = split_known_sequence(following, database)
            following_complete = find_candidates(following, database).status in {"exact", "alias"} or len(following_parts) > 1
            quantity_start = bool(re.match(r"^[^,;]*?\(?[\d,.]+\s*(?:ppm|ppb|%)\)?", text, re.I))
            if previous_complete and (following_complete or quantity_start):
                separator = ", "
                boundary_proposals = True
        joined += separator
        cursor = len(joined)
        joined += text
        source_spans.append((cursor, len(joined), indices))
    output = []
    search_start = 0
    for token in normalize_text(joined):
        start = joined.find(token.raw_text, search_start)
        end = start + len(token.raw_text)
        search_start = end
        indices = tuple(dict.fromkeys(index for left, right, group in source_spans if left < end and right > start for index in group))
        parts = split_known_sequence(token.name, database)
        for part in parts:
            match = find_candidates(part, database, MatchSettings())
            _, cleanup_changes = clean_ocr_fragment(token.name)
            changes = [*token.transformations, *cleanup_changes, *match.transformations]
            if len(entries) > 1:
                changes.append("물리적 줄바꿈 연결")
            if re.search(r"\(\s*[*※]", ocr.raw_text):
                changes.append("목록 뒤 별표 안내문 분리·원문 보존")
            if boundary_proposals:
                changes.append("줄 경계의 완결 성분 사이에 구분자 보완 제안")
            if len(parts) > 1:
                changes.append("누락 구분자를 사전 이름·제한된 교정 후보로 분리 제안")
            name, status = part.strip(), "unmatched"
            if match.status in {"exact", "alias"}:
                name = match.candidates[0].name
                status = match.status
                if name != part.strip():
                    changes.append("정식명·별칭 표기 정리")
            elif _can_propose_spelling(part, match):
                name = match.candidates[0].name
                status = "correction_proposed"
                changes.append("제한된 철자 교정 제안·미확정")
            elif match.candidates:
                status = "needs_review"
            raw = token.raw_text.strip() if len(parts) == 1 else part
            output.append(IngredientDraft(raw, name, status, indices, tuple(dict.fromkeys(changes)), match.candidates,
                                          original_fragment=token.raw_text))
    return tuple(output)


def dictionary_coverage(text: str, database: IngredientDatabase) -> float:
    tokens = normalize_text(text)
    if not tokens:
        return 0.0
    return sum(bool(database.find(clean_ocr_fragment(token.name)[0])) for token in tokens) / len(tokens)
