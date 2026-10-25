"""입력·출력 규격. 모르는 함량은 0이 아닌 None으로 남긴다."""
from dataclasses import dataclass, field
from typing import Literal

Origin = Literal["석유계", "식물성", "기타", "확인 필요"]
ORIGINS = ("석유계", "식물성", "기타", "확인 필요")
UNCERTAINTIES = {"db_missing", "name_unresolved", "origin_uncertain", "evidence_insufficient"}


@dataclass(frozen=True)
class Token:
    raw_text: str
    name: str
    position: int
    transformations: tuple[str, ...] = ()


@dataclass(frozen=True)
class OCRBlock:
    raw_text: str
    bbox: tuple[tuple[float, float], ...]
    confidence: float
    source_index: int


@dataclass(frozen=True)
class OCRLine:
    raw_text: str
    source_indices: tuple[int, ...]


@dataclass(frozen=True)
class OCRResult:
    status: str
    raw_text: str = ""
    blocks: tuple[OCRBlock, ...] = ()
    lines: tuple[OCRLine, ...] = ()
    suppressed_indices: tuple[int, ...] = ()
    message: str = ""
    reading_order: str = "rows"


@dataclass(frozen=True)
class OCRToken:
    token: Token
    source_indices: tuple[int, ...]


@dataclass(frozen=True)
class Candidate:
    name: str
    matched_name: str
    method: str
    score: float


@dataclass(frozen=True)
class MatchResult:
    raw_text: str
    normalized: str
    status: str
    candidates: tuple[Candidate, ...]
    score_gap: float | None = None
    # 검색 결과는 확정 결과가 아니다. 이름은 사용자 동작으로만 선택한다.
    confirmed: bool = False
    cleaned_text: str = ""
    transformations: tuple[str, ...] = ()


@dataclass(frozen=True)
class IngredientDraft:
    raw_text: str
    name: str
    status: str
    source_indices: tuple[int, ...] = ()
    transformations: tuple[str, ...] = ()
    candidates: tuple[Candidate, ...] = ()
    confirmed: bool = False
    original_fragment: str = ""


@dataclass(frozen=True)
class IngredientScan:
    status: str
    ocr: OCRResult
    ingredients: tuple[IngredientDraft, ...] = ()
    processing: dict = field(default_factory=dict)
    passes: tuple[dict, ...] = ()
    warnings: tuple[str, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class ConfirmedIngredient:
    name: str
    amount: float | None = None
    unit: str = "%"
    basis: str = "mass"


@dataclass(frozen=True)
class IngredientRecord:
    name: str
    aliases: tuple[str, ...]
    origin: Origin
    reason: str
    functions: tuple[str, ...] = ()
    source_url: str = ""
    checked_on: str = ""
    uncertainty_reason: str = ""


@dataclass(frozen=True)
class CautionRecord:
    name: str
    reason: str
    restriction: str
    country: str
    product_type: str
    use_condition: str
    concentration_condition: str
    source_url: str
    checked_on: str


@dataclass(frozen=True)
class ClassifiedIngredient:
    confirmed: ConfirmedIngredient
    canonical_name: str
    origin: Origin
    reason: str
    uncertainty_reason: str
    match_method: str
    functions: tuple[str, ...] = ()
    source_url: str = ""
    checked_on: str = ""


@dataclass(frozen=True)
class RatioResult:
    values: dict[str, float]
    denominator: float
    label: str
    unit: str
    basis: str


@dataclass(frozen=True)
class AnalysisResult:
    status: str
    dataset_kind: str
    input_records: tuple[ConfirmedIngredient, ...]
    rows: tuple[ClassifiedIngredient, ...]
    duplicates: tuple[str, ...]
    count_ratio: RatioResult | None
    amount_ratio: RatioResult | None
    cautions: dict[str, tuple[CautionRecord, ...]] = field(default_factory=dict)
