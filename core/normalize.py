"""원문을 보존하며 구분자와 문자 폭만 정리한다. 화학 이름을 추측하지 않는다."""
import re
import unicodedata

from core.models import Token

DASHES = str.maketrans({char: "-" for char in "‐‑‒–—−﹘﹣－"})
BRACKETS = {"(": ")", "[": "]", "【": "】", "〈": "〉", "{": "}"}


def search_view(text: str) -> tuple[str, str, tuple[int, ...]]:
    """검색 키와 정규화된 원문에서의 문자 위치를 함께 만든다. 숫자·슬래시·괄호는 지우지 않는다."""
    normalized = unicodedata.normalize("NFKC", text).translate(DASHES)
    chars, positions = [], []
    for i, char in enumerate(normalized):
        if char.isspace() or unicodedata.category(char) == "Cf":
            continue
        for lower in char.casefold():
            chars.append(lower)
            positions.append(i)
    return normalized, "".join(chars), tuple(positions)


def bracket_pairs(text: str) -> tuple[tuple[int, int], ...]:
    stack, pairs = [], []
    for i, char in enumerate(text):
        char = unicodedata.normalize("NFKC", char)
        if char in BRACKETS:
            stack.append((i, char))
        elif char in BRACKETS.values() and stack and BRACKETS[stack[-1][1]] == char:
            start, _ = stack.pop()
            pairs.append((start, i))
    return tuple(pairs)


def clean_ocr_fragment(text: str) -> tuple[str, tuple[str, ...]]:
    normalized = unicodedata.normalize("NFKC", text)
    changes = []
    if normalized != text:
        changes.append("문자 폭 정리(NFKC)")
    formatted = "".join(char for char in normalized if unicodedata.category(char) != "Cf")
    if formatted != normalized:
        changes.append("보이지 않는 서식 문자 제거")
    dashed = formatted.translate(DASHES)
    if dashed != formatted:
        changes.append("하이픈 표기 통일")
    paired = {i for left, right in bracket_pairs(dashed) for i in (left, right)}
    left, right = 0, len(dashed)
    bracket_chars = {*BRACKETS, *BRACKETS.values()}
    decoration = set(":：•▪■●◆※")
    while left < right and (dashed[left].isspace() or dashed[left] in decoration or dashed[left] in bracket_chars and left not in paired):
        left += 1
    while right > left and (dashed[right - 1].isspace() or dashed[right - 1] in decoration or dashed[right - 1] in bracket_chars and right - 1 not in paired):
        right -= 1
    cleaned = dashed[left:right]
    if cleaned != dashed.strip():
        changes.append("이름 경계의 짝 없는 괄호·구분 기호 정리")
    collapsed = re.sub(r"\s+", " ", cleaned).strip()
    if collapsed != cleaned:
        changes.append("공백 정리")
    return collapsed, tuple(changes)


def normalize_key(name: str) -> str:
    return search_view(name)[1]


def normalize_text(raw_text: str) -> list[Token]:
    """입력: 원문. 처리: 괄호·숫자 쉼표 보호. 출력: 추적 가능한 조각들."""
    chunks: list[str] = []
    start = 0
    # 닫히지 않은 '[' 하나가 이후 모든 쉼표를 가리지 않게, 실제로 짝이 있는 범위만 보호한다.
    difference = [0] * (len(raw_text) + 1)
    for left, right in bracket_pairs(raw_text):
        difference[left] += 1
        difference[right + 1] -= 1
    depth = 0
    for i, char in enumerate(raw_text):
        depth += difference[i]
        # 1,2-처럼 이름 앞의 위치 번호만 보호한다. CI 77891,0O에서
        # 서로 다른 두 항목을 단지 숫자가 이웃했다는 이유로 합치지 않는다.
        prefix = normalize_key(clean_ocr_fragment(raw_text[start:i])[0]) if char in ",，" else ""
        suffix = normalize_key(raw_text[i + 1:]) if char in ",，" else ""
        is_numeric_comma = (
            char in ",，" and re.fullmatch(r"\d+(?:,\d+)*", prefix) is not None
            and re.match(r"\d+(?:,\d+)*[-‐‑–]", suffix) is not None
        )
        if depth == 0 and char in ",，;；\n\r·•" and not is_numeric_comma:
            chunks.append(raw_text[start:i])
            start = i + 1
    chunks.append(raw_text[start:])
    result = []
    for position, raw in enumerate(chunks):
        normalized = unicodedata.normalize("NFKC", raw)
        name = re.sub(r"\s+", " ", normalized).strip()
        if name:
            changes = []
            if normalized != raw:
                changes.append("문자 폭 정리(NFKC)")
            if name != normalized:
                changes.append("공백 정리")
            result.append(Token(raw, name, position, tuple(changes)))
    return result
