"""공통 규격 v1. 필드·함수 이름 변경은 C가 모아서 반영한다."""
from dataclasses import dataclass
from typing import Literal

from core.models import (
    AnalysisResult, Candidate, ConfirmedIngredient, IngredientDraft, IngredientScan,
)
from core.scan import ScanOutput

CONTRACT_VERSION = 1
PIPELINE_VERSION = "starter-1"
Mode = Literal["count", "partial", "full"]


@dataclass(frozen=True)
class AnalysisRequest:
    # C가 사용자의 최종 확인 뒤에만 생성한다. 후보 검색 결과를 바로 전달하지 않는다.
    ingredients: tuple[ConfirmedIngredient, ...]
    mode: Mode = "count"


SESSION_DEFAULTS = {
    "source_key": None,
    "source_error": None,
    "scan_output": None,
    "stage": "idle",
    "input_text": "",
    "retry_nonce": 0,
    "review_signature": None,
    "result": None,
}
