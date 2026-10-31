"""공통 규격 v3(자동 분석 선택·v1/v2 기본값 호환). 필드·함수 이름 변경은 C가 모아서 반영한다."""
from dataclasses import dataclass
from typing import Literal

from core.models import (
    AnalysisResult, AutomaticDecision, Candidate, ConfirmedIngredient, IngredientDraft, IngredientScan,
)
from core.scan import ScanOutput

CONTRACT_VERSION = 3
PIPELINE_VERSION = "ppocr-v5-korean-1"
Mode = Literal["count", "partial", "full"]


@dataclass(frozen=True)
class AnalysisRequest:
    # 기본은 기존 확정 목록. automatic=True는 사용자가 요청한 자동 선택 정책이다.
    ingredients: tuple[ConfirmedIngredient, ...]
    mode: Mode = "count"
    automatic: bool = False
    automatic_decisions: tuple[AutomaticDecision, ...] = ()


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
